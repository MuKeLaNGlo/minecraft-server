from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from api.auth import CurrentUser, require_role
from core.config import config, PLUGIN_LOADERS
from db.database import db
from services.modrinth import modrinth

router = APIRouter(prefix="/api/mods", tags=["mods"])

_SIDE_LABELS = {
    "required": "обязателен",
    "optional": "опционально",
    "unsupported": "не нужен",
}


def _format_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except (ValueError, AttributeError):
        return None


def _get_manager():
    if config.mc_loader in PLUGIN_LOADERS:
        from minecraft.plugin_manager import plugin_manager
        return plugin_manager
    else:
        from minecraft.mod_manager import mod_manager
        return mod_manager


@router.get("")
async def list_installed(user: Annotated[CurrentUser, require_role("admin")]):
    mgr = _get_manager()
    rows = await mgr.list_installed()
    return [
        {
            "id": r[0],
            "slug": r[1],
            "name": r[2],
            "version_id": r[3],
            "filename": r[4],
            "game_version": r[6] if len(r) > 6 else None,
            "loader": r[7] if len(r) > 7 else None,
            "installed_at": r[8] if len(r) > 8 else None,
        }
        for r in rows
    ]


@router.get("/search")
async def search_mods(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
    user: CurrentUser = None,
):
    mgr = _get_manager()
    is_plugin = config.mc_loader in PLUGIN_LOADERS
    project_type = "plugin" if is_plugin else "mod"

    results = await modrinth.search(q, limit=limit, project_type=project_type)
    hits = results.get("hits", [])

    return {
        "hits": [
            {
                "slug": h.get("slug"),
                "title": h.get("title"),
                "description": h.get("description", ""),
                "downloads": h.get("downloads", 0),
                "icon_url": h.get("icon_url", ""),
            }
            for h in hits
        ],
        "total": results.get("total_hits", 0),
    }


@router.get("/project/{slug}")
async def mod_detail(slug: str, user: CurrentUser = None):
    """Get detailed info about a mod from Modrinth."""
    project = await modrinth.get_project(slug)
    versions = await modrinth.get_versions(slug)
    latest_version = versions[0]["version_number"] if versions else None

    categories = project.get("categories", [])
    license_info = project.get("license", {})
    license_id = (
        license_info.get("id", None) if isinstance(license_info, dict)
        else str(license_info) if license_info else None
    )

    server_side = project.get("server_side", "unknown")
    client_side = project.get("client_side", "unknown")

    installed = await db.mod_installed(slug)

    return {
        "slug": slug,
        "title": project.get("title", slug),
        "description": project.get("description", ""),
        "body": project.get("body", ""),
        "icon_url": project.get("icon_url", ""),
        "downloads": project.get("downloads", 0),
        "followers": project.get("followers", 0),
        "updated": _format_date(project.get("updated", "")),
        "published": _format_date(project.get("published", "")),
        "categories": categories,
        "license": license_id,
        "source_url": project.get("source_url", ""),
        "wiki_url": project.get("wiki_url", ""),
        "issues_url": project.get("issues_url", ""),
        "server_side": server_side,
        "server_side_label": _SIDE_LABELS.get(server_side, server_side),
        "client_side": client_side,
        "client_side_label": _SIDE_LABELS.get(client_side, client_side),
        "is_client_only": server_side == "unsupported",
        "latest_version": latest_version,
        "loader": config.mc_loader,
        "game_version": config.mc_version,
        "installed": installed,
        "modrinth_url": f"https://modrinth.com/mod/{slug}",
        "gallery": [
            img.get("url") for img in project.get("gallery", [])
            if img.get("url")
        ][:5],
    }


@router.post("/{slug}/install")
async def install_mod(slug: str, user: Annotated[CurrentUser, require_role("admin")]):
    mgr = _get_manager()
    is_plugin = config.mc_loader in PLUGIN_LOADERS
    if is_plugin:
        result = await mgr.install_plugin(slug)
    else:
        result = await mgr.install_mod(slug)
    return result


@router.delete("/{slug}")
async def remove_mod(slug: str, user: Annotated[CurrentUser, require_role("admin")]):
    mgr = _get_manager()
    is_plugin = config.mc_loader in PLUGIN_LOADERS
    if is_plugin:
        result = await mgr.remove_plugin(slug)
    else:
        result = await mgr.remove_mod(slug)
    return result


@router.post("/check-updates")
async def check_updates(user: Annotated[CurrentUser, require_role("admin")]):
    mgr = _get_manager()
    updates = await mgr.check_updates()
    return {"updates": updates}
