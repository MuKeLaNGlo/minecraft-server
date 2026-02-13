import aiosqlite
from typing import List, Optional, Any

from core.config import config


class Database:
    def __init__(self):
        self.con: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self.con = await aiosqlite.connect(config.db_path)
        await self.con.execute("PRAGMA journal_mode=WAL")
        await self._init_tables()

    async def disconnect(self) -> None:
        if self.con:
            await self.con.close()

    async def _init_tables(self) -> None:
        await self.con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS black_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS installed_mods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                version_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                sha512 TEXT,
                game_version TEXT,
                loader TEXT,
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                size_bytes INTEGER,
                world_name TEXT DEFAULT 'world',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                extra_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS player_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                left_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_player
                ON player_sessions(player_name);
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await self.con.commit()

    # --- helpers ---

    async def execute(self, query: str, params: tuple = ()) -> None:
        await self.con.execute(query, params)
        await self.con.commit()

    async def fetch_all(self, query: str, params: tuple = ()) -> List[Any]:
        async with self.con.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Any]:
        async with self.con.execute(query, params) as cursor:
            return await cursor.fetchone()

    # --- users ---

    async def add_user(self, telegram_id: str) -> bool:
        try:
            await self.execute(
                "INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,)
            )
            return True
        except aiosqlite.IntegrityError:
            return False

    async def user_exists(self, telegram_id: str) -> bool:
        row = await self.fetch_one(
            "SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        return row is not None

    async def user_remove(self, telegram_id: str) -> bool:
        await self.execute(
            "DELETE FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        return True

    # --- admins ---

    async def add_admin(self, telegram_id: str) -> bool:
        try:
            await self.execute(
                "INSERT INTO admins (telegram_id) VALUES (?)", (telegram_id,)
            )
            return True
        except aiosqlite.IntegrityError:
            return False

    async def check_admin(self, telegram_id: str) -> bool:
        row = await self.fetch_one(
            "SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,)
        )
        return row is not None

    async def admin_remove(self, telegram_id: str) -> bool:
        await self.execute(
            "DELETE FROM admins WHERE telegram_id = ?", (telegram_id,)
        )
        return True

    # --- blacklist ---

    async def add_black_list(self, command: str) -> bool:
        try:
            await self.execute(
                "INSERT INTO black_list (command) VALUES (?)", (command.lower(),)
            )
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_black_list(self, command: str) -> bool:
        await self.execute(
            "DELETE FROM black_list WHERE command = ?", (command.lower(),)
        )
        return True

    async def command_exists(self, command: str) -> bool:
        row = await self.fetch_one(
            "SELECT 1 FROM black_list WHERE command = ?", (command.lower(),)
        )
        return row is not None

    async def commands_all(self) -> List[str]:
        rows = await self.fetch_all("SELECT command FROM black_list")
        return [r[0] for r in rows]

    # --- installed mods ---

    async def add_mod(
        self,
        slug: str,
        name: str,
        version_id: str,
        filename: str,
        sha512: str,
        game_version: str,
        loader: str,
    ) -> bool:
        try:
            await self.execute(
                """INSERT INTO installed_mods
                   (slug, name, version_id, filename, sha512, game_version, loader)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (slug, name, version_id, filename, sha512, game_version, loader),
            )
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_mod(self, slug: str) -> bool:
        await self.execute("DELETE FROM installed_mods WHERE slug = ?", (slug,))
        return True

    async def get_installed_mods(self) -> List[Any]:
        return await self.fetch_all(
            "SELECT id, slug, name, version_id, filename, sha512, game_version, loader, installed_at "
            "FROM installed_mods ORDER BY name"
        )

    async def mod_installed(self, slug: str) -> bool:
        row = await self.fetch_one(
            "SELECT 1 FROM installed_mods WHERE slug = ?", (slug,)
        )
        return row is not None

    async def get_mod_by_slug(self, slug: str) -> Optional[Any]:
        return await self.fetch_one(
            "SELECT id, slug, name, version_id, filename, sha512, game_version, loader "
            "FROM installed_mods WHERE slug = ?",
            (slug,),
        )

    # --- backups ---

    async def add_backup(
        self, filename: str, size_bytes: int, world_name: str = "world"
    ) -> bool:
        try:
            await self.execute(
                "INSERT INTO backups (filename, size_bytes, world_name) VALUES (?, ?, ?)",
                (filename, size_bytes, world_name),
            )
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_backups(self) -> List[Any]:
        return await self.fetch_all(
            "SELECT id, filename, size_bytes, world_name, created_at "
            "FROM backups ORDER BY created_at DESC"
        )

    async def get_backup_by_id(self, bak_id: int) -> Optional[Any]:
        return await self.fetch_one(
            "SELECT id, filename, size_bytes, world_name, created_at "
            "FROM backups WHERE id = ?",
            (bak_id,),
        )

    async def remove_backup(self, filename: str) -> bool:
        await self.execute("DELETE FROM backups WHERE filename = ?", (filename,))
        return True

    # --- scheduled tasks ---

    async def add_scheduled_task(
        self, task_type: str, cron_expression: str, extra_data: str = None
    ) -> int:
        await self.execute(
            "INSERT INTO scheduled_tasks (task_type, cron_expression, extra_data) VALUES (?, ?, ?)",
            (task_type, cron_expression, extra_data),
        )
        row = await self.fetch_one("SELECT last_insert_rowid()")
        return row[0]

    async def get_scheduled_tasks(self) -> List[Any]:
        return await self.fetch_all(
            "SELECT id, task_type, cron_expression, enabled, extra_data, created_at "
            "FROM scheduled_tasks ORDER BY id"
        )

    async def toggle_scheduled_task(self, task_id: int, enabled: bool) -> None:
        await self.execute(
            "UPDATE scheduled_tasks SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, task_id),
        )

    async def remove_scheduled_task(self, task_id: int) -> None:
        await self.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))

    # --- bot settings ---

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.fetch_one(
            "SELECT value FROM bot_settings WHERE key = ?", (key,)
        )
        return row[0] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.con.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await self.con.commit()

    async def get_all_settings(self) -> dict:
        rows = await self.fetch_all("SELECT key, value FROM bot_settings")
        return {r[0]: r[1] for r in rows}

    # --- player sessions ---

    async def open_session(self, player_name: str) -> int:
        await self.execute(
            "INSERT INTO player_sessions (player_name, joined_at) VALUES (?, datetime('now'))",
            (player_name,),
        )
        row = await self.fetch_one("SELECT last_insert_rowid()")
        return row[0]

    async def close_session(self, player_name: str) -> None:
        await self.execute(
            """UPDATE player_sessions SET left_at = datetime('now')
               WHERE id = (
                   SELECT id FROM player_sessions
                   WHERE player_name = ? AND left_at IS NULL
                   ORDER BY joined_at DESC LIMIT 1
               )""",
            (player_name,),
        )

    async def close_all_sessions(self) -> None:
        await self.execute(
            "UPDATE player_sessions SET left_at = datetime('now') WHERE left_at IS NULL"
        )

    async def get_player_stats(self, player_name: str) -> Optional[Any]:
        row = await self.fetch_one(
            """SELECT
                   COUNT(*) as session_count,
                   COALESCE(SUM(
                       CAST((julianday(COALESCE(left_at, datetime('now'))) - julianday(joined_at)) * 86400 AS INTEGER)
                   ), 0) as total_seconds,
                   MAX(joined_at) as last_seen
               FROM player_sessions WHERE player_name = ?""",
            (player_name,),
        )
        current = await self.fetch_one(
            "SELECT joined_at FROM player_sessions WHERE player_name = ? AND left_at IS NULL",
            (player_name,),
        )
        if not row or row[0] == 0:
            return None
        return {
            "session_count": row[0],
            "total_seconds": row[1],
            "last_seen": row[2],
            "online": current is not None,
            "current_session_start": current[0] if current else None,
        }

    async def get_all_player_stats(self) -> List[Any]:
        return await self.fetch_all(
            """SELECT
                   player_name,
                   COUNT(*) as session_count,
                   COALESCE(SUM(
                       CAST((julianday(COALESCE(left_at, datetime('now'))) - julianday(joined_at)) * 86400 AS INTEGER)
                   ), 0) as total_seconds,
                   MAX(joined_at) as last_seen,
                   MAX(CASE WHEN left_at IS NULL THEN 1 ELSE 0 END) as is_online
               FROM player_sessions
               GROUP BY player_name
               ORDER BY total_seconds DESC"""
        )


    async def get_recent_players(self, hours: int = 24) -> List[Any]:
        """Get players active in the last N hours, sorted: online first, then by last_seen desc."""
        return await self.fetch_all(
            """SELECT
                   player_name,
                   MAX(COALESCE(left_at, datetime('now'))) as last_seen,
                   MAX(CASE WHEN left_at IS NULL THEN 1 ELSE 0 END) as is_online
               FROM player_sessions
               WHERE joined_at >= datetime('now', ? || ' hours')
                  OR left_at IS NULL
               GROUP BY player_name
               ORDER BY is_online DESC, last_seen DESC""",
            (str(-hours),),
        )


db = Database()
