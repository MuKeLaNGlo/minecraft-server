import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from minecraft.docker_manager import docker_manager
from utils.logger import logger

# Log line patterns
# Forge format:  [Server thread/INFO] [minecraft/MinecraftServer]: Player joined the game
# Vanilla/Paper: [Server thread/INFO]: Player joined the game
# Purpur/Paper:  [18:51:23 INFO]: Player joined the game
# Also strip ANSI escape codes and Minecraft color codes first
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|>\.\.\.\.\[K|\[m|§[0-9a-fk-or]")
JOIN_RE = re.compile(r"INFO\].*?:\s+(\w+) joined the game")
LEAVE_RE = re.compile(r"INFO\].*?:\s+(\w+) left the game")
CHAT_RE = re.compile(r"INFO\].*?:\s+<(\w+)>\s+(.+)")
READY_RE = re.compile(r"INFO\].*?:\s+Done \(([0-9.]+)s\)!")

EventHandler = Callable[["LogEvent"], Awaitable[None]]


@dataclass
class LogEvent:
    event_type: str  # "join", "leave", "chat", "server_ready"
    player_name: str = ""
    message: Optional[str] = None  # "chat" text or startup time for "server_ready"
    raw_line: str = ""


class LogWatcher:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._last_poll: Optional[datetime] = None

    def on(self, event_type: str, handler: EventHandler) -> None:
        """Register an event handler."""
        self._handlers.setdefault(event_type, []).append(handler)

    async def start(self, interval: float = 3.0) -> None:
        self._running = True
        self._interval = interval
        self._last_poll = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._loop())
        logger.info(f"LogWatcher started (interval={interval}s)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("LogWatcher stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._poll()
            except Exception as e:
                logger.warning(f"LogWatcher poll error: {e}")
            await asyncio.sleep(self._interval)

    async def _poll(self) -> None:
        if not await docker_manager.is_running():
            return

        since = self._last_poll
        now = datetime.now(timezone.utc)

        raw = await docker_manager.logs_since(since)
        self._last_poll = now
        if not raw:
            return

        for line in raw.strip().splitlines():
            # Docker timestamps format: "2024-01-15T12:34:56.789Z log content"
            # Strip the timestamp prefix if present
            content = line
            if len(line) > 31 and line[0].isdigit():
                content = line[31:].strip() if " " in line[:35] else line

            event = self._parse_line(content)
            if event:
                event.raw_line = line
                await self._dispatch(event)

    def _parse_line(self, line: str) -> Optional[LogEvent]:
        line = _ANSI_RE.sub("", line)
        match = JOIN_RE.search(line)
        if match:
            return LogEvent(event_type="join", player_name=match.group(1))

        match = LEAVE_RE.search(line)
        if match:
            return LogEvent(event_type="leave", player_name=match.group(1))

        match = CHAT_RE.search(line)
        if match:
            return LogEvent(
                event_type="chat",
                player_name=match.group(1),
                message=match.group(2),
            )

        match = READY_RE.search(line)
        if match:
            return LogEvent(
                event_type="server_ready",
                message=match.group(1),  # startup time in seconds
            )

        return None

    async def replay_missed_logs(self, since: datetime) -> list[tuple[str, str, str]]:
        """Parse old logs since a timestamp and return session events.

        Returns list of (event_type, player_name, utc_timestamp_str)
        where event_type is "join" or "leave".
        Does NOT dispatch to handlers (no notifications sent).
        """
        if not await docker_manager.is_running():
            return []

        raw = await docker_manager.logs_since(since)
        if not raw:
            return []

        events = []
        for line in raw.strip().splitlines():
            # Docker timestamp: "2024-01-15T12:34:56.789012345Z log content"
            ts_str = None
            content = line
            if len(line) > 31 and line[0].isdigit():
                ts_str = line[:30].strip()
                content = line[31:].strip() if " " in line[:35] else line

            event = self._parse_line(content)
            if event and event.event_type in ("join", "leave"):
                utc_str = self._docker_ts_to_sqlite(ts_str)
                events.append((event.event_type, event.player_name, utc_str))

        return events

    @staticmethod
    def _docker_ts_to_sqlite(ts_str: str | None) -> str:
        """Convert Docker timestamp to SQLite datetime string."""
        if ts_str:
            try:
                clean_ts = ts_str.rstrip("Z")
                if "." in clean_ts:
                    base, frac = clean_ts.split(".", 1)
                    clean_ts = f"{base}.{frac[:6]}"
                dt = datetime.fromisoformat(clean_ts).replace(tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, IndexError):
                pass
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    async def _dispatch(self, event: LogEvent) -> None:
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.warning(f"LogWatcher handler error ({event.event_type}): {e}")


log_watcher = LogWatcher()
