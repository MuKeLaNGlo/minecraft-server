import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set

import aiohttp

from core.config import config
from db.database import db
from services.modrinth import modrinth
from utils.logger import logger


class ModManager:
    def __init__(self):
        self.mods_dir = Path(config.mc_data_path) / "mods"

    async def _resolve_dependencies(
        self, version: Dict, _seen: Optional[Set[str]] = None
    ) -> List[Dict]:
        """Recursively resolve required dependencies for a version.

        Returns list of {"project_id", "slug", "name"} for deps that need installing.
        """
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

            # Check if already installed (by slug or project_id)
            try:
                project = await modrinth.get_project(project_id)
            except Exception:
                continue
            slug = project.get("slug", project_id)
            name = project.get("title", slug)

            if await db.mod_installed(slug):
                continue

            # Check compatible versions exist
            dep_versions = await modrinth.get_versions(slug)
            if not dep_versions:
                continue

            deps_to_install.append({
                "project_id": project_id,
                "slug": slug,
                "name": name,
            })

            # Recurse into this dependency's own dependencies
            sub_deps = await self._resolve_dependencies(dep_versions[0], _seen)
            deps_to_install.extend(sub_deps)

        return deps_to_install

    async def install_mod_with_deps(self, project_slug: str) -> Dict:
        """Install a mod and all its required dependencies.

        Returns {success, name, version, filename, deps: [{name, version, filename}]}.
        """
        # First resolve what we need to install
        if await db.mod_installed(project_slug):
            return {"success": False, "error": "Мод уже установлен."}

        versions = await modrinth.get_versions(project_slug)
        if not versions:
            return {"success": False, "error": "Нет совместимых версий для текущего лоадера/версии."}

        version = versions[0]
        deps = await self._resolve_dependencies(version)

        # Install dependencies first
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
                logger.warning(f"Dep install failed ({dep['slug']}): {result.get('error')}")

        # Install the main mod
        result = await self._install_single(project_slug)
        result["deps"] = installed_deps
        return result

    async def _install_single(self, project_slug: str) -> Dict:
        """Download and install a single mod (no dependency resolution)."""
        # Get compatible versions
        versions = await modrinth.get_versions(project_slug)
        if not versions:
            return {"success": False, "error": "Нет совместимых версий для текущего лоадера/версии."}

        version = versions[0]  # Latest compatible
        primary_file = None
        for f in version.get("files", []):
            if f.get("primary", False):
                primary_file = f
                break
        if not primary_file:
            primary_file = version["files"][0] if version["files"] else None
        if not primary_file:
            return {"success": False, "error": "Файл мода не найден."}

        url = primary_file["url"]
        filename = primary_file["filename"]
        expected_sha512 = primary_file.get("hashes", {}).get("sha512", "")

        # Check if already installed
        if await db.mod_installed(project_slug):
            return {"success": False, "error": "Мод уже установлен."}

        # Download
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
        except Exception as e:
            logger.error(f"Mod download failed: {e}")
            return {"success": False, "error": f"Ошибка скачивания: {e}"}

        # Verify hash
        if expected_sha512:
            actual_sha512 = hashlib.sha512(data).hexdigest()
            if actual_sha512 != expected_sha512:
                return {
                    "success": False,
                    "error": "Хеш файла не совпадает! Загрузка отменена.",
                }
        else:
            actual_sha512 = hashlib.sha512(data).hexdigest()

        # Save to mods directory
        self.mods_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.mods_dir / filename
        filepath.write_bytes(data)

        # Get project info for display name
        try:
            project = await modrinth.get_project(project_slug)
            name = project.get("title", project_slug)
        except Exception:
            name = project_slug

        # Save to database
        await db.add_mod(
            slug=project_slug,
            name=name,
            version_id=version["id"],
            filename=filename,
            sha512=actual_sha512,
            game_version=config.mc_version,
            loader=config.mc_loader,
        )

        logger.info(f"Mod installed: {name} ({filename})")
        return {
            "success": True,
            "name": name,
            "filename": filename,
            "version": version.get("version_number", "?"),
        }

    async def install_mod(self, project_slug: str) -> Dict:
        """Install a mod with automatic dependency resolution."""
        return await self.install_mod_with_deps(project_slug)

    async def remove_mod(self, slug: str) -> Dict:
        """Remove mod file and database record."""
        mod = await db.get_mod_by_slug(slug)
        if not mod:
            return {"success": False, "error": "Мод не найден в базе данных."}

        filename = mod[4]  # filename column
        filepath = self.mods_dir / filename
        if filepath.exists():
            filepath.unlink()

        name = mod[2]  # name column
        await db.remove_mod(slug)
        logger.info(f"Mod removed: {name} ({filename})")
        return {"success": True, "name": name}

    async def list_installed(self) -> List:
        return await db.get_installed_mods()

    async def check_updates(self) -> List[Dict]:
        """Check all installed mods for available updates."""
        mods = await db.get_installed_mods()
        hashes = []
        hash_to_mod = {}
        for mod in mods:
            sha512 = mod[5]  # sha512 column
            if sha512:
                hashes.append(sha512)
                hash_to_mod[sha512] = {
                    "slug": mod[1],
                    "name": mod[2],
                    "current_version_id": mod[3],
                }

        if not hashes:
            return []

        try:
            updates = await modrinth.check_updates(hashes)
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return []

        results = []
        for old_hash, new_version in updates.items():
            mod_info = hash_to_mod.get(old_hash)
            if not mod_info:
                continue
            if new_version.get("id") != mod_info["current_version_id"]:
                results.append(
                    {
                        "slug": mod_info["slug"],
                        "name": mod_info["name"],
                        "new_version": new_version.get("version_number", "?"),
                        "new_version_id": new_version.get("id"),
                    }
                )

        return results


mod_manager = ModManager()
