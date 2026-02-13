import asyncio
import os
import shutil
import tarfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from core.config import config
from db.database import db
from minecraft.rcon import rcon
from utils.logger import logger


class BackupManager:
    def __init__(self):
        self.mc_data = Path(config.mc_data_path)
        self.backup_dir = Path(config.backups_path)

    async def create_backup(self, world_name: str = "world") -> Dict:
        """Create backup: save-off -> save-all -> tar.gz -> save-on."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        world_path = self.mc_data / world_name

        if not world_path.exists():
            return {"success": False, "error": f"Мир '{world_name}' не найден."}

        # Disable saving and flush
        await rcon.execute("save-off")
        await rcon.execute("save-all flush")
        await asyncio.sleep(3)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{world_name}_{timestamp}.tar.gz"
        filepath = self.backup_dir / filename

        try:
            size = await asyncio.to_thread(self._create_tar, filepath, world_path, world_name)
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            await rcon.execute("save-on")

        await db.add_backup(filename, size, world_name)
        logger.info(f"Backup created: {filename} ({size} bytes)")

        return {"success": True, "filename": filename, "size": size}

    def _create_tar(self, filepath: Path, world_path: Path, arcname: str) -> int:
        with tarfile.open(filepath, "w:gz") as tar:
            tar.add(str(world_path), arcname=arcname)
        return os.path.getsize(filepath)

    async def list_backups(self) -> List:
        return await db.get_backups()

    async def restore_backup(self, filename: str) -> Dict:
        """Restore world from backup. Server must be stopped."""
        filepath = self.backup_dir / filename
        if not filepath.exists():
            return {"success": False, "error": "Файл бэкапа не найден."}

        # Get world_name from DB (reliable) instead of parsing from filename
        row = await db.fetch_one(
            "SELECT world_name FROM backups WHERE filename = ?", (filename,)
        )
        world_name = row[0] if row else "world"
        target = self.mc_data / world_name

        try:
            await asyncio.to_thread(self._restore, filepath, target)
        except Exception as e:
            logger.error(f"Backup restore failed: {e}")
            return {"success": False, "error": str(e)}

        logger.info(f"Backup restored: {filename}")
        return {"success": True, "world_name": world_name}

    def _restore(self, filepath: Path, target: Path) -> None:
        if target.exists():
            shutil.rmtree(target)
        with tarfile.open(filepath, "r:gz") as tar:
            tar.extractall(str(target.parent))

    async def rotate_backups(self, keep: int = 10) -> int:
        """Delete oldest backups beyond keep count."""
        backups = sorted(
            self.backup_dir.glob("backup_*.tar.gz"), key=os.path.getmtime
        )
        removed = 0
        while len(backups) > keep:
            oldest = backups.pop(0)
            oldest.unlink()
            await db.remove_backup(oldest.name)
            removed += 1
            logger.info(f"Rotated backup: {oldest.name}")
        return removed

    def get_backup_path(self, filename: str) -> Optional[Path]:
        filepath = self.backup_dir / filename
        return filepath if filepath.exists() else None


backup_manager = BackupManager()
