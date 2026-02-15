import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from core.config import config
from minecraft.server_config import server_config
from utils.logger import logger

# itzg/minecraft-server runs as uid=1000 gid=1000 inside the container.
# Bot runs as root, so we must chown world dirs to match.
_MC_UID = 1000
_MC_GID = 1000

# Paper/Purpur/Spigot split dimensions into separate directories:
#   world/          — overworld
#   world_nether/   — the nether
#   world_the_end/  — the end
_DIMENSION_SUFFIXES = ("_nether", "_the_end")


class WorldManager:
    def __init__(self):
        self.data_path = Path(config.mc_data_path)

    # ── Dimension helpers ─────────────────────────────────────────

    def get_dimension_dirs(self, world_name: str) -> List[Path]:
        """Return list of existing dimension directories for a world.

        Always includes the base world dir first (if exists), then
        _nether, _the_end if they exist.
        """
        dirs = []
        base = self.data_path / world_name
        if base.exists():
            dirs.append(base)
        for suffix in _DIMENSION_SUFFIXES:
            dim_dir = self.data_path / f"{world_name}{suffix}"
            if dim_dir.exists():
                dirs.append(dim_dir)
        return dirs

    def get_all_dimension_names(self, world_name: str) -> List[str]:
        """Return list of all dimension directory names (existing or not)."""
        return [world_name] + [f"{world_name}{s}" for s in _DIMENSION_SUFFIXES]

    def _is_dimension_dir(self, dir_name: str) -> bool:
        """Check if a directory name is a dimension sub-dir of some world."""
        for suffix in _DIMENSION_SUFFIXES:
            if dir_name.endswith(suffix):
                base = dir_name[: -len(suffix)]
                base_path = self.data_path / base
                if base_path.exists() and (base_path / "level.dat").exists():
                    return True
        return False

    # ── List worlds ───────────────────────────────────────────────

    async def list_worlds(self) -> List[Dict]:
        """List all world directories, grouping dimensions together.

        Dimension dirs (_nether, _the_end) are NOT shown as separate worlds.
        Their size is summed into the base world.
        """
        worlds = []
        if not self.data_path.exists():
            return worlds

        skip = {
            "logs", "config", "mods", "plugins", "crash-reports", "libraries",
            "defaultconfigs", "patchouli_books", "resources", "scripts",
            "cache", "versions",
        }

        for entry in sorted(self.data_path.iterdir()):
            if not entry.is_dir() or entry.name.startswith(".") or entry.name in skip:
                continue
            # Skip dimension directories — they'll be included with their base world
            if self._is_dimension_dir(entry.name):
                continue

            has_level = (entry / "level.dat").exists()
            is_empty_world = not any(entry.iterdir()) if not has_level else False
            if not has_level and not is_empty_world:
                continue

            # Sum up size of all dimension dirs
            total_size = 0.0
            dim_dirs = self.get_dimension_dirs(entry.name)
            dim_count = len(dim_dirs)
            if has_level:
                for d in dim_dirs:
                    total_size += await self._get_dir_size_mb(d)

            mtime = datetime.fromtimestamp(entry.stat().st_mtime)
            worlds.append({
                "name": entry.name,
                "size_mb": total_size,
                "last_modified": mtime,
                "generated": has_level,
                "dimensions": dim_count,
            })
        return worlds

    async def get_current_world(self) -> str:
        """Get current world name from server.properties."""
        return server_config.get_property("level-name") or "world"

    # ── Switch ────────────────────────────────────────────────────

    async def switch_world(self, world_name: str) -> Dict:
        """Switch active world by updating level-name in server.properties."""
        world_dir = self.data_path / world_name
        if not world_dir.exists():
            return {"success": False, "error": f"Мир '{world_name}' не найден."}

        current = await self.get_current_world()
        if current == world_name:
            return {"success": False, "error": f"Мир '{world_name}' уже активен."}

        # Fix ownership on all dimension dirs
        for d in self.get_dimension_dirs(world_name):
            self._fix_ownership(d)

        ok = server_config.write_property("level-name", world_name)
        if not ok:
            return {"success": False, "error": "Не удалось обновить server.properties."}

        logger.info(f"World switched: {current} -> {world_name}")
        return {"success": True, "message": f"Мир переключён на '{world_name}'. Перезапусти сервер."}

    # ── Create ────────────────────────────────────────────────────

    async def create_world(self, name: str) -> Dict:
        """Create a new empty world directory."""
        if not name or "/" in name or "\\" in name or ".." in name:
            return {"success": False, "error": "Недопустимое имя мира."}

        world_dir = self.data_path / name
        if world_dir.exists():
            return {"success": False, "error": f"Мир '{name}' уже существует."}

        try:
            world_dir.mkdir(parents=True)
            os.chown(world_dir, _MC_UID, _MC_GID)
            logger.info(f"World created: {name}")
            return {
                "success": True,
                "message": f"Мир '{name}' создан. Переключись на него и запусти сервер — мир сгенерируется автоматически.",
            }
        except Exception as e:
            return {"success": False, "error": f"Ошибка создания: {e}"}

    # ── Delete ────────────────────────────────────────────────────

    async def delete_world(self, name: str) -> Dict:
        """Delete a world and all its dimension directories."""
        current = await self.get_current_world()
        if name == current:
            return {"success": False, "error": "Нельзя удалить активный мир. Сначала переключись на другой."}

        world_dir = self.data_path / name
        if not world_dir.exists():
            return {"success": False, "error": f"Мир '{name}' не найден."}

        try:
            # Delete all dimension dirs
            for d in self.get_dimension_dirs(name):
                await asyncio.to_thread(shutil.rmtree, d)
                logger.info(f"Deleted dimension dir: {d.name}")
            logger.info(f"World deleted: {name} (with all dimensions)")
            return {"success": True, "message": f"Мир '{name}' удалён (включая все измерения)."}
        except Exception as e:
            return {"success": False, "error": f"Ошибка удаления: {e}"}

    # ── Rename ────────────────────────────────────────────────────

    async def rename_world(self, old_name: str, new_name: str) -> Dict:
        """Rename a world and all its dimension directories."""
        if not new_name or "/" in new_name or "\\" in new_name or ".." in new_name:
            return {"success": False, "error": "Недопустимое имя мира."}

        old_dir = self.data_path / old_name
        new_dir = self.data_path / new_name

        if not old_dir.exists():
            return {"success": False, "error": f"Мир '{old_name}' не найден."}
        if new_dir.exists():
            return {"success": False, "error": f"Мир '{new_name}' уже существует."}

        try:
            # Rename all dimension dirs
            for suffix in ("",) + _DIMENSION_SUFFIXES:
                src = self.data_path / f"{old_name}{suffix}"
                dst = self.data_path / f"{new_name}{suffix}"
                if src.exists():
                    await asyncio.to_thread(src.rename, dst)
                    logger.info(f"Renamed: {src.name} -> {dst.name}")

            # If renaming the current world, update server.properties
            current = await self.get_current_world()
            if current == old_name:
                server_config.write_property("level-name", new_name)

            logger.info(f"World renamed: {old_name} -> {new_name} (with dimensions)")
            return {"success": True, "message": f"Мир переименован: '{old_name}' → '{new_name}' (включая измерения)."}
        except Exception as e:
            return {"success": False, "error": f"Ошибка переименования: {e}"}

    # ── Clone ─────────────────────────────────────────────────────

    async def clone_world(self, name: str, clone_name: str) -> Dict:
        """Clone a world and all its dimension directories."""
        if not clone_name or "/" in clone_name or "\\" in clone_name or ".." in clone_name:
            return {"success": False, "error": "Недопустимое имя мира."}

        src = self.data_path / name
        dst = self.data_path / clone_name

        if not src.exists():
            return {"success": False, "error": f"Мир '{name}' не найден."}
        if dst.exists():
            return {"success": False, "error": f"Мир '{clone_name}' уже существует."}

        try:
            # Clone all dimension dirs
            for suffix in ("",) + _DIMENSION_SUFFIXES:
                s = self.data_path / f"{name}{suffix}"
                d = self.data_path / f"{clone_name}{suffix}"
                if s.exists():
                    await asyncio.to_thread(shutil.copytree, s, d)
                    self._fix_ownership(d)
                    logger.info(f"Cloned: {s.name} -> {d.name}")

            logger.info(f"World cloned: {name} -> {clone_name} (with dimensions)")
            return {
                "success": True,
                "message": f"Мир '{name}' клонирован как '{clone_name}' (включая измерения).",
            }
        except Exception as e:
            return {"success": False, "error": f"Ошибка клонирования: {e}"}

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _fix_ownership(world_dir: Path) -> None:
        """Recursively chown world directory to MC server uid:gid."""
        try:
            stat = world_dir.stat()
            if stat.st_uid != _MC_UID or stat.st_gid != _MC_GID:
                for root, dirs, files in os.walk(world_dir):
                    os.chown(root, _MC_UID, _MC_GID)
                    for f in files:
                        os.chown(os.path.join(root, f), _MC_UID, _MC_GID)
                logger.info(f"Fixed ownership for world dir: {world_dir.name}")
        except Exception as e:
            logger.warning(f"Failed to fix ownership for {world_dir}: {e}")

    async def _get_dir_size_mb(self, path: Path) -> float:
        """Get directory size in MB using du command."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "du", "-sm", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            size_str = stdout.decode().split("\t")[0].strip()
            return float(size_str)
        except Exception:
            return 0.0


world_manager = WorldManager()
