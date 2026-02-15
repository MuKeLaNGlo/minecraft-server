import hashlib
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set

import aiohttp

from core.config import config, PLUGIN_LOADERS
from db.database import db
from services.modrinth import modrinth
from utils.logger import logger


def _plugin_loaders() -> list[str]:
    """Return loaders list for Modrinth API queries.

    Purpur is Paper-compatible, so we search for both.
    """
    loader = config.mc_loader
    if loader == "purpur":
        return ["purpur", "paper"]
    if loader == "paper":
        return ["paper"]
    if loader == "spigot":
        return ["spigot", "bukkit"]
    return [loader]


class PluginManager:
    def __init__(self):
        self.plugins_dir = Path(config.mc_data_path) / "plugins"

    async def _resolve_dependencies(
        self, version: Dict, _seen: Optional[Set[str]] = None
    ) -> List[Dict]:
        """Recursively resolve required dependencies for a version."""
        if _seen is None:
            _seen = set()

        deps_to_install = []
        for dep in version.get("dependencies", []):
            if dep.get("dependency_type") != "required":
                continue
            project_id = dep.get("project_id")
            if not project_id or project_id in _seen:
                continue
            _seen.add(project_id)

            try:
                project = await modrinth.get_project(project_id)
            except Exception:
                continue
            slug = project.get("slug", project_id)
            name = project.get("title", slug)

            if await db.plugin_installed(slug):
                continue

            dep_versions = await modrinth.get_versions(
                slug, loaders=_plugin_loaders(),
            )
            if not dep_versions:
                continue

            deps_to_install.append({
                "project_id": project_id,
                "slug": slug,
                "name": name,
            })

            sub_deps = await self._resolve_dependencies(dep_versions[0], _seen)
            deps_to_install.extend(sub_deps)

        return deps_to_install

    async def install_plugin_with_deps(self, project_slug: str) -> Dict:
        """Install a plugin and all its required dependencies."""
        if await db.plugin_installed(project_slug):
            return {"success": False, "error": "Плагин уже установлен."}

        versions = await modrinth.get_versions(
            project_slug, loaders=_plugin_loaders(),
        )
        if not versions:
            return {"success": False, "error": "Нет совместимых версий для текущего загрузчика/версии."}

        version = versions[0]
        deps = await self._resolve_dependencies(version)

        installed_deps = []
        for dep in deps:
            result = await self._install_single(dep["slug"])
            if result["success"]:
                installed_deps.append({
                    "name": result["name"],
                    "version": result["version"],
                    "filename": result["filename"],
                })
            else:
                logger.warning(f"Plugin dep install failed ({dep['slug']}): {result.get('error')}")

        result = await self._install_single(project_slug)
        result["deps"] = installed_deps
        return result

    async def _install_single(self, project_slug: str) -> Dict:
        """Download and install a single plugin."""
        versions = await modrinth.get_versions(
            project_slug, loaders=_plugin_loaders(),
        )
        if not versions:
            return {"success": False, "error": "Нет совместимых версий для текущего загрузчика/версии."}

        version = versions[0]
        primary_file = None
        for f in version.get("files", []):
            if f.get("primary", False):
                primary_file = f
                break
        if not primary_file:
            primary_file = version["files"][0] if version["files"] else None
        if not primary_file:
            return {"success": False, "error": "Файл плагина не найден."}

        url = primary_file["url"]
        filename = primary_file["filename"]
        expected_sha512 = primary_file.get("hashes", {}).get("sha512", "")

        if await db.plugin_installed(project_slug):
            return {"success": False, "error": "Плагин уже установлен."}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
        except Exception as e:
            logger.error(f"Plugin download failed: {e}")
            return {"success": False, "error": f"Ошибка скачивания: {e}"}

        if expected_sha512:
            actual_sha512 = hashlib.sha512(data).hexdigest()
            if actual_sha512 != expected_sha512:
                return {
                    "success": False,
                    "error": "Хеш файла не совпадает! Загрузка отменена.",
                }
        else:
            actual_sha512 = hashlib.sha512(data).hexdigest()

        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.plugins_dir / filename
        filepath.write_bytes(data)

        try:
            project = await modrinth.get_project(project_slug)
            name = project.get("title", project_slug)
        except Exception:
            name = project_slug

        await db.add_plugin(
            slug=project_slug,
            name=name,
            version_id=version["id"],
            filename=filename,
            sha512=actual_sha512,
            game_version=config.mc_version,
            loader=config.mc_loader,
        )

        logger.info(f"Plugin installed: {name} ({filename})")
        return {
            "success": True,
            "name": name,
            "filename": filename,
            "version": version.get("version_number", "?"),
        }

    async def install_plugin(self, project_slug: str) -> Dict:
        """Install a plugin with automatic dependency resolution."""
        return await self.install_plugin_with_deps(project_slug)

    async def remove_plugin(self, slug: str) -> Dict:
        """Remove plugin file and database record."""
        plugin = await db.get_plugin_by_slug(slug)
        if not plugin:
            return {"success": False, "error": "Плагин не найден в базе данных."}

        filename = plugin[4]
        filepath = self.plugins_dir / filename
        if filepath.exists():
            filepath.unlink()

        name = plugin[2]
        await db.remove_plugin(slug)
        logger.info(f"Plugin removed: {name} ({filename})")
        return {"success": True, "name": name}

    async def sync_plugins_dir(self) -> Dict:
        """Scan plugins directory and sync with DB."""
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        disk_files: dict[str, Path] = {}
        for f in self.plugins_dir.iterdir():
            if f.is_file() and f.suffix == ".jar":
                disk_files[f.name] = f

        db_plugins = await db.get_installed_plugins()
        db_filenames = {p[4]: p for p in db_plugins}

        added = []
        removed = []

        for filename, filepath in disk_files.items():
            if filename not in db_filenames:
                sha512 = hashlib.sha512(filepath.read_bytes()).hexdigest()
                slug = filename.replace(".jar", "")
                name = slug

                try:
                    version_info = await modrinth.get_version_by_hash(sha512)
                    if version_info:
                        project_id = version_info.get("project_id", "")
                        if project_id:
                            project = await modrinth.get_project(project_id)
                            slug = project.get("slug", slug)
                            name = project.get("title", name)
                except Exception:
                    pass

                await db.add_plugin(
                    slug=slug,
                    name=name,
                    version_id="unknown",
                    filename=filename,
                    sha512=sha512,
                    game_version=config.mc_version,
                    loader=config.mc_loader,
                )
                added.append(filename)
                logger.info(f"Synced untracked plugin: {filename}")

        for filename, plugin_row in db_filenames.items():
            if filename not in disk_files:
                slug = plugin_row[1]
                await db.remove_plugin(slug)
                removed.append(filename)
                logger.info(f"Removed stale plugin DB entry: {filename}")

        return {"added": added, "removed": removed}

    async def install_from_file(self, filename: str, data: bytes) -> Dict:
        """Install a plugin from uploaded file bytes."""
        if not filename.endswith(".jar"):
            return {"success": False, "error": "Файл должен быть .jar"}

        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.plugins_dir / filename

        if filepath.exists():
            return {"success": False, "error": f"Файл {filename} уже существует."}

        filepath.write_bytes(data)
        sha512 = hashlib.sha512(data).hexdigest()

        slug = filename.replace(".jar", "")
        await db.add_plugin(
            slug=slug,
            name=slug,
            version_id="manual",
            filename=filename,
            sha512=sha512,
            game_version=config.mc_version,
            loader=config.mc_loader,
        )
        logger.info(f"Plugin installed from file: {filename}")
        return {"success": True, "filename": filename}

    async def preview_upload(self, filename: str, data: bytes) -> Dict:
        """Validate upload and preview what would be installed."""
        if not filename.lower().endswith(".jar"):
            return {"success": False, "error": "Поддерживаются только .jar файлы."}

        exists = (self.plugins_dir / filename).exists()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jar") as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        return {
            "success": True,
            "is_archive": False,
            "tmp_path": tmp_path,
            "original_name": filename,
            "new": [] if exists else [filename],
            "existing": [filename] if exists else [],
        }

    async def install_pending(self, tmp_path: str, original_name: str, is_archive: bool) -> Dict:
        """Install from a previously saved temp file."""
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        installed = []
        skipped = []
        errors = []

        try:
            data = Path(tmp_path).read_bytes()
            result = await self.install_from_file(original_name, data)
            if result["success"]:
                installed.append(original_name)
            else:
                err = result.get("error", "")
                if "уже существует" in err:
                    skipped.append(original_name)
                else:
                    errors.append(f"{original_name}: {err}")
        except Exception as e:
            return {"success": False, "error": f"Ошибка установки: {e}"}
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return {
            "success": len(installed) > 0 or len(skipped) > 0,
            "installed": installed,
            "skipped": skipped,
            "errors": errors,
        }

    async def list_installed(self) -> List:
        return await db.get_installed_plugins()

    async def check_updates(self) -> List[Dict]:
        """Check all installed plugins for available updates."""
        plugins = await db.get_installed_plugins()
        hashes = []
        hash_to_plugin = {}
        for p in plugins:
            sha512 = p[5]
            if sha512:
                hashes.append(sha512)
                hash_to_plugin[sha512] = {
                    "slug": p[1],
                    "name": p[2],
                    "current_version_id": p[3],
                }

        if not hashes:
            return []

        try:
            updates = await modrinth.check_updates(
                hashes, loaders=_plugin_loaders(),
            )
        except Exception as e:
            logger.error(f"Plugin update check failed: {e}")
            return []

        results = []
        for old_hash, new_version in updates.items():
            info = hash_to_plugin.get(old_hash)
            if not info:
                continue
            if new_version.get("id") != info["current_version_id"]:
                results.append({
                    "slug": info["slug"],
                    "name": info["name"],
                    "new_version": new_version.get("version_number", "?"),
                    "new_version_id": new_version.get("id"),
                })

        return results


plugin_manager = PluginManager()
