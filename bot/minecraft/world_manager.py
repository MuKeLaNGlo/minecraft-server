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


class WorldManager:
    def __init__(self):
        self.data_path = Path(config.mc_data_path)

    async def list_worlds(self) -> List[Dict]:
        """List all world directories (generated or empty/new)."""
        worlds = []
        if not self.data_path.exists():
            return worlds

        # Skip known non-world directories
        skip = {
            "logs", "config", "mods", "plugins", "crash-reports", "libraries",
            "defaultconfigs", "patchouli_books", "resources", "scripts",
        }

        for entry in sorted(self.data_path.iterdir()):
            if not entry.is_dir() or entry.name.startswith(".") or entry.name in skip:
                continue
            has_level = (entry / "level.dat").exists()
            # Include if has level.dat OR is an empty dir (newly created world)
            is_empty_world = not any(entry.iterdir()) if not has_level else False
            if has_level or is_empty_world:
                size_mb = await self._get_dir_size_mb(entry) if has_level else 0.0
                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                worlds.append({
                    "name": entry.name,
                    "size_mb": size_mb,
                    "last_modified": mtime,
                    "generated": has_level,
                })
        return worlds

    async def get_current_world(self) -> str:
        """Get current world name from server.properties."""
        return server_config.get_property("level-name") or "world"

    async def switch_world(self, world_name: str) -> Dict:
        """Switch active world by updating level-name in server.properties."""
        world_dir = self.data_path / world_name
        if not world_dir.exists():
            return {"success": False, "error": f"Мир '{world_name}' не найден."}

        current = await self.get_current_world()
        if current == world_name:
            return {"success": False, "error": f"Мир '{world_name}' уже активен."}

        ok = server_config.write_property("level-name", world_name)
        if not ok:
            return {"success": False, "error": "Не удалось обновить server.properties."}

        logger.info(f"World switched: {current} -> {world_name}")
        return {"success": True, "message": f"Мир переключён на '{world_name}'. Перезапусти сервер."}

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

    async def delete_world(self, name: str) -> Dict:
        """Delete a world directory. Cannot delete current active world."""
        current = await self.get_current_world()
        if name == current:
            return {"success": False, "error": "Нельзя удалить активный мир. Сначала переключись на другой."}

        world_dir = self.data_path / name
        if not world_dir.exists():
            return {"success": False, "error": f"Мир '{name}' не найден."}

        try:
            await asyncio.to_thread(shutil.rmtree, world_dir)
            logger.info(f"World deleted: {name}")
            return {"success": True, "message": f"Мир '{name}' удалён."}
        except Exception as e:
            return {"success": False, "error": f"Ошибка удаления: {e}"}

    async def rename_world(self, old_name: str, new_name: str) -> Dict:
        """Rename a world directory."""
        if not new_name or "/" in new_name or "\\" in new_name or ".." in new_name:
            return {"success": False, "error": "Недопустимое имя мира."}

        old_dir = self.data_path / old_name
        new_dir = self.data_path / new_name

        if not old_dir.exists():
            return {"success": False, "error": f"Мир '{old_name}' не найден."}
        if new_dir.exists():
            return {"success": False, "error": f"Мир '{new_name}' уже существует."}

        try:
            await asyncio.to_thread(old_dir.rename, new_dir)

            # If renaming the current world, update server.properties
            current = await self.get_current_world()
            if current == old_name:
                server_config.write_property("level-name", new_name)

            logger.info(f"World renamed: {old_name} -> {new_name}")
            return {"success": True, "message": f"Мир переименован: '{old_name}' → '{new_name}'."}
        except Exception as e:
            return {"success": False, "error": f"Ошибка переименования: {e}"}

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
