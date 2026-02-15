import hashlib
import os
import subprocess
import tarfile
import zipfile
import tempfile
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

        # Get project info for display name and side info
        client_side = "unknown"
        server_side = "unknown"
        try:
            project = await modrinth.get_project(project_slug)
            name = project.get("title", project_slug)
            client_side = project.get("client_side", "unknown")
            server_side = project.get("server_side", "unknown")
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
            client_side=client_side,
            server_side=server_side,
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

    async def sync_mods_dir(self) -> Dict:
        """Scan mods directory and sync with DB.

        Returns {added: [filenames], removed: [filenames]}.
        """
        self.mods_dir.mkdir(parents=True, exist_ok=True)

        # Files on disk
        disk_files: dict[str, Path] = {}
        for f in self.mods_dir.iterdir():
            if f.is_file() and f.suffix == ".jar":
                disk_files[f.name] = f

        # Files in DB
        db_mods = await db.get_installed_mods()
        db_filenames = {mod[4]: mod for mod in db_mods}  # filename -> row

        added = []
        removed = []

        # Add mods that are on disk but not in DB
        for filename, filepath in disk_files.items():
            if filename not in db_filenames:
                sha512 = hashlib.sha512(filepath.read_bytes()).hexdigest()
                # Try to guess slug from filename (remove version/loader suffix)
                slug = filename.replace(".jar", "")
                name = slug  # Use filename as display name
                client_side = "unknown"
                server_side = "unknown"

                # Try to identify mod via Modrinth hash lookup
                try:
                    version_info = await modrinth.get_version_by_hash(sha512)
                    if version_info:
                        project_id = version_info.get("project_id", "")
                        if project_id:
                            project = await modrinth.get_project(project_id)
                            slug = project.get("slug", slug)
                            name = project.get("title", name)
                            client_side = project.get("client_side", "unknown")
                            server_side = project.get("server_side", "unknown")
                except Exception:
                    pass  # API failed, keep defaults

                await db.add_mod(
                    slug=slug,
                    name=name,
                    version_id="unknown",
                    filename=filename,
                    sha512=sha512,
                    game_version=config.mc_version,
                    loader=config.mc_loader,
                    client_side=client_side,
                    server_side=server_side,
                )
                added.append(filename)
                logger.info(f"Synced untracked mod: {filename}")

        # Remove DB entries for mods that no longer exist on disk
        for filename, mod_row in db_filenames.items():
            if filename not in disk_files:
                slug = mod_row[1]
                await db.remove_mod(slug)
                removed.append(filename)
                logger.info(f"Removed stale DB entry: {filename}")

        return {"added": added, "removed": removed}

    async def install_from_file(self, filename: str, data: bytes) -> Dict:
        """Install a mod from uploaded file bytes.

        Returns {success, filename}.
        """
        if not filename.endswith(".jar"):
            return {"success": False, "error": "Файл должен быть .jar"}

        self.mods_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.mods_dir / filename

        # Don't overwrite existing
        if filepath.exists():
            return {"success": False, "error": f"Файл {filename} уже существует."}

        filepath.write_bytes(data)
        sha512 = hashlib.sha512(data).hexdigest()

        slug = filename.replace(".jar", "")
        await db.add_mod(
            slug=slug,
            name=slug,
            version_id="manual",
            filename=filename,
            sha512=sha512,
            game_version=config.mc_version,
            loader=config.mc_loader,
        )
        logger.info(f"Mod installed from file: {filename}")
        return {"success": True, "filename": filename}

    def _extract_jars(self, filename: str, tmp_path: str) -> List[tuple[str, bytes]]:
        """Extract (name, bytes) pairs of .jar files from an archive."""
        lower = filename.lower()
        jars: List[tuple[str, bytes]] = []

        if lower.endswith(".zip"):
            with zipfile.ZipFile(tmp_path, "r") as zf:
                for name in zf.namelist():
                    basename = Path(name).name
                    if basename.endswith(".jar") and basename:
                        jars.append((basename, zf.read(name)))

        elif lower.endswith((".tar.gz", ".tgz", ".tar")):
            with tarfile.open(tmp_path, "r:*") as tf:
                for member in tf.getmembers():
                    basename = Path(member.name).name
                    if basename.endswith(".jar") and member.isfile():
                        f = tf.extractfile(member)
                        if f:
                            jars.append((basename, f.read()))

        return jars

    async def preview_upload(self, filename: str, data: bytes) -> Dict:
        """Validate upload and preview what would be installed.

        Saves data to a temp file for later install_pending().
        Returns {success, tmp_path, new: [names], existing: [names], error?}.
        """
        lower = filename.lower()
        _ARCHIVE_EXTS = (".zip", ".tar.gz", ".tgz", ".tar", ".rar")
        is_jar = lower.endswith(".jar")
        is_archive = any(lower.endswith(ext) for ext in _ARCHIVE_EXTS)

        if is_jar:
            exists = (self.mods_dir / filename).exists()
            # Save jar to temp for install_pending
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

        if not is_archive:
            return {"success": False, "error": "Неподдерживаемый формат."}

        # Save archive to temp
        suffix = "".join(Path(filename).suffixes[-2:]) or ".zip"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            if lower.endswith(".rar"):
                rar_jars = await self._extract_rar_jars(tmp_path)
                if rar_jars is None:
                    os.unlink(tmp_path)
                    return {"success": False, "error": "Не удалось распаковать RAR."}
                jar_names = [name for name, _ in rar_jars]
            else:
                jar_files = self._extract_jars(filename, tmp_path)
                jar_names = [name for name, _ in jar_files]
        except Exception as e:
            os.unlink(tmp_path)
            return {"success": False, "error": f"Ошибка чтения архива: {e}"}

        if not jar_names:
            os.unlink(tmp_path)
            return {"success": False, "error": "В архиве нет .jar файлов."}

        new = [n for n in jar_names if not (self.mods_dir / n).exists()]
        existing = [n for n in jar_names if (self.mods_dir / n).exists()]

        return {
            "success": True,
            "is_archive": True,
            "tmp_path": tmp_path,
            "original_name": filename,
            "new": new,
            "existing": existing,
        }

    async def install_pending(self, tmp_path: str, original_name: str, is_archive: bool) -> Dict:
        """Install from a previously saved temp file. Cleans up tmp_path after.

        Returns {success, installed: [filenames], skipped: [filenames], errors: [str]}.
        """
        self.mods_dir.mkdir(parents=True, exist_ok=True)
        installed = []
        skipped = []
        errors = []

        try:
            if not is_archive:
                # Single .jar
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
            else:
                # Archive — re-extract and install
                lower = original_name.lower()
                if lower.endswith(".rar"):
                    jar_files = await self._extract_rar_jars(tmp_path)
                    if jar_files is None:
                        return {"success": False, "error": "Ошибка RAR."}
                else:
                    jar_files = self._extract_jars(original_name, tmp_path)

                for basename, jar_data in jar_files:
                    result = await self.install_from_file(basename, jar_data)
                    if result["success"]:
                        installed.append(basename)
                    else:
                        err = result.get("error", "")
                        if "уже существует" in err:
                            skipped.append(basename)
                        else:
                            errors.append(f"{basename}: {err}")
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

    async def install_from_archive(self, filename: str, data: bytes) -> Dict:
        """Legacy: extract .jar files from an archive and install immediately."""
        preview = await self.preview_upload(filename, data)
        if not preview["success"]:
            return preview
        return await self.install_pending(
            preview["tmp_path"], preview["original_name"], preview["is_archive"]
        )

    async def _extract_rar_jars(self, rar_path: str) -> Optional[List[tuple[str, bytes]]]:
        """Extract .jar files from a RAR archive using unrar CLI."""
        tmp_dir = tempfile.mkdtemp()
        try:
            proc = subprocess.run(
                ["unrar", "e", "-o-", rar_path, tmp_dir],
                capture_output=True, timeout=60,
            )
            if proc.returncode not in (0, 1):  # 1 = warnings (e.g. skipped existing)
                return None
            jars = []
            for f in Path(tmp_dir).iterdir():
                if f.is_file() and f.suffix == ".jar":
                    jars.append((f.name, f.read_bytes()))
            return jars
        except FileNotFoundError:
            return None
        except Exception:
            return None
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    async def install_from_zip(self, zip_data: bytes) -> Dict:
        """Legacy wrapper — delegates to install_from_archive."""
        return await self.install_from_archive("archive.zip", zip_data)

    async def enrich_mod_sides(self) -> int:
        """Update client_side/server_side for mods that have 'unknown'.

        Tries Modrinth hash lookup, then project lookup by slug.
        Returns number of mods updated.
        """
        mods = await db.get_installed_mods()
        updated = 0
        for mod in mods:
            slug = mod[1]
            sha512 = mod[5]
            # Check if side info already known (columns 8,9 if present)
            # Since installed_mods may not have these columns in the tuple yet,
            # we query directly
            row = await db.fetch_one(
                "SELECT client_side, server_side FROM installed_mods WHERE slug = ?",
                (slug,),
            )
            if not row:
                continue
            if row[0] != "unknown":
                continue  # already enriched

            client_side = "unknown"
            server_side = "unknown"
            try:
                # Try hash lookup first
                if sha512:
                    version_info = await modrinth.get_version_by_hash(sha512)
                    if version_info:
                        project_id = version_info.get("project_id", "")
                        if project_id:
                            project = await modrinth.get_project(project_id)
                            client_side = project.get("client_side", "unknown")
                            server_side = project.get("server_side", "unknown")
                # Fallback: try slug lookup (works for Modrinth-installed mods)
                if client_side == "unknown" and slug and slug != "unknown":
                    try:
                        project = await modrinth.get_project(slug)
                        client_side = project.get("client_side", "unknown")
                        server_side = project.get("server_side", "unknown")
                    except Exception:
                        pass
            except Exception:
                pass

            if client_side != "unknown":
                await db.update_mod_sides(slug, client_side, server_side)
                updated += 1

        return updated

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
