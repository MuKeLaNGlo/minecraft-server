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

    async def create_backup(self, world_name: str | None = None) -> Dict:
        """Create backup of a world and all its dimensions.

        Paper/Purpur stores dimensions as separate dirs:
          world/, world_nether/, world_the_end/
        All are included in a single archive.
        """
        from minecraft.world_manager import world_manager

        if world_name is None:
            world_name = await world_manager.get_current_world()

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Collect all dimension dirs that exist
        dim_dirs = world_manager.get_dimension_dirs(world_name)
        if not dim_dirs:
            return {"success": False, "error": f"Мир '{world_name}' не найден."}

        # Disable saving and flush
        await rcon.execute("save-off")
        await rcon.execute("save-all flush")
        await asyncio.sleep(3)

        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        filename = f"backup_{world_name}_{timestamp}.tar.gz"
        filepath = self.backup_dir / filename

        try:
            size = await asyncio.to_thread(self._create_tar, filepath, dim_dirs)
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            await rcon.execute("save-on")

        await db.add_backup(filename, size, world_name)
        dim_names = [d.name for d in dim_dirs]
        logger.info(f"Backup created: {filename} ({size} bytes), dirs: {dim_names}")

        return {"success": True, "filename": filename, "size": size, "dimensions": len(dim_dirs)}

    def _create_tar(self, filepath: Path, dim_dirs: List[Path]) -> int:
        """Create tar.gz archive containing all dimension directories."""
        with tarfile.open(filepath, "w:gz") as tar:
            for d in dim_dirs:
                tar.add(str(d), arcname=d.name)
        return os.path.getsize(filepath)

    async def list_backups(self) -> List:
        return await db.get_backups()

    async def restore_backup(self, filename: str) -> Dict:
        """Restore world from backup (all dimensions). Server must be stopped."""
        filepath = self.backup_dir / filename
        if not filepath.exists():
            return {"success": False, "error": "Файл бэкапа не найден."}

        row = await db.fetch_one(
            "SELECT world_name FROM backups WHERE filename = ?", (filename,)
        )
        world_name = row[0] if row else "world"

        try:
            restored_dirs = await asyncio.to_thread(
                self._restore, filepath, world_name
            )
        except Exception as e:
            logger.error(f"Backup restore failed: {e}")
            return {"success": False, "error": str(e)}

        # Fix ownership on restored dirs
        from minecraft.world_manager import world_manager
        for d in restored_dirs:
            world_manager._fix_ownership(d)

        logger.info(f"Backup restored: {filename}, dirs: {[d.name for d in restored_dirs]}")
        return {"success": True, "world_name": world_name, "dimensions": len(restored_dirs)}

    def _restore(self, filepath: Path, world_name: str) -> List[Path]:
        """Extract backup, removing old dimension dirs first.

        Returns list of restored directory Paths.
        """
        from minecraft.world_manager import world_manager

        # Peek inside archive to see what dirs are in there
        with tarfile.open(filepath, "r:gz") as tar:
            top_dirs = {m.name.split("/")[0] for m in tar.getmembers()}

        # Remove existing dirs that will be replaced
        restored = []
        for dir_name in top_dirs:
            target = self.mc_data / dir_name
            if target.exists():
                shutil.rmtree(target)
            restored.append(target)

        # Extract
        with tarfile.open(filepath, "r:gz") as tar:
            tar.extractall(str(self.mc_data))

        return restored

    async def restore_as_copy(self, filename: str, new_name: str) -> Dict:
        """Restore backup into new world directories (clone)."""
        filepath = self.backup_dir / filename
        if not filepath.exists():
            return {"success": False, "error": "Файл бэкапа не найден."}

        target = self.mc_data / new_name
        if target.exists():
            return {"success": False, "error": f"Мир '{new_name}' уже существует."}

        row = await db.fetch_one(
            "SELECT world_name FROM backups WHERE filename = ?", (filename,)
        )
        original_world = row[0] if row else "world"

        try:
            restored_dirs = await asyncio.to_thread(
                self._restore_as_copy, filepath, original_world, new_name
            )
        except Exception as e:
            logger.error(f"Backup restore-as-copy failed: {e}")
            return {"success": False, "error": str(e)}

        from minecraft.world_manager import world_manager
        for d in restored_dirs:
            world_manager._fix_ownership(d)

        logger.info(f"Backup cloned: {filename} -> {new_name}, dirs: {[d.name for d in restored_dirs]}")
        return {"success": True, "world_name": new_name, "dimensions": len(restored_dirs)}

    def _restore_as_copy(
        self, filepath: Path, original_world: str, new_name: str
    ) -> List[Path]:
        """Extract backup, renaming dirs from original_world to new_name.

        E.g. 'World 1' -> 'MyWorld', 'World 1_nether' -> 'MyWorld_nether'
        """
        tmp_dir = self.mc_data / f".tmp_restore_{new_name}"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)

        with tarfile.open(filepath, "r:gz") as tar:
            tar.extractall(str(tmp_dir))

        restored = []
        for entry in sorted(tmp_dir.iterdir()):
            if not entry.is_dir():
                continue
            # Determine new name: replace original_world prefix with new_name
            if entry.name == original_world:
                new_dir_name = new_name
            elif entry.name.startswith(f"{original_world}_"):
                suffix = entry.name[len(original_world):]
                new_dir_name = f"{new_name}{suffix}"
            else:
                new_dir_name = entry.name

            target = self.mc_data / new_dir_name
            if target.exists():
                shutil.rmtree(target)
            entry.rename(target)
            restored.append(target)

        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)

        if not restored:
            raise RuntimeError("Не удалось найти мир в архиве бэкапа.")

        return restored

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

    async def delete_backup(self, filename: str) -> Dict:
        """Delete a single backup file and its DB record."""
        filepath = self.backup_dir / filename
        try:
            if filepath.exists():
                filepath.unlink()
            await db.remove_backup(filename)
            logger.info(f"Backup deleted: {filename}")
            return {"success": True}
        except Exception as e:
            logger.error(f"Backup delete failed: {e}")
            return {"success": False, "error": str(e)}

    def get_backup_path(self, filename: str) -> Optional[Path]:
        filepath = self.backup_dir / filename
        return filepath if filepath.exists() else None


backup_manager = BackupManager()
