from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import FileResponse

from api.auth import CurrentUser, require_role
from db.database import db
from minecraft.backup_manager import backup_manager
from minecraft.world_manager import world_manager
from utils.formatting import format_bytes

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.get("")
async def list_backups(user: Annotated[CurrentUser, require_role("admin")]):
    rows = await backup_manager.list_backups()
    return [
        {
            "id": r[0],
            "filename": r[1],
            "size": r[2],
            "size_str": format_bytes(r[2]) if r[2] else "?",
            "world": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]


@router.post("")
async def create_backup(user: Annotated[CurrentUser, require_role("admin")]):
    result = await backup_manager.create_backup()
    return result


@router.post("/{bak_id}/restore")
async def restore_backup(bak_id: int, user: Annotated[CurrentUser, require_role("admin")]):
    from minecraft.docker_manager import docker_manager
    if await docker_manager.is_running():
        return {"success": False, "error": "Server must be stopped first"}

    row = await db.get_backup_by_id(bak_id)
    if not row:
        return {"success": False, "error": "Backup not found"}

    filename = row[1]
    result = await backup_manager.restore_backup(filename)
    return result


@router.delete("/{bak_id}")
async def delete_backup(bak_id: int, user: Annotated[CurrentUser, require_role("admin")]):
    row = await db.get_backup_by_id(bak_id)
    if not row:
        return {"success": False, "error": "Backup not found"}

    filename = row[1]
    result = await backup_manager.delete_backup(filename)
    return result


@router.get("/{bak_id}/download")
async def download_backup(bak_id: int, user: Annotated[CurrentUser, require_role("admin")]):
    row = await db.get_backup_by_id(bak_id)
    if not row:
        return {"success": False, "error": "Backup not found"}

    filename = row[1]
    path = backup_manager.get_backup_path(filename)
    if not path:
        return {"success": False, "error": "File not found on disk"}

    return FileResponse(path, filename=filename, media_type="application/gzip")
