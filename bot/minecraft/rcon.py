import asyncio
import signal
import platform
from typing import Optional
from unittest.mock import patch

from mcrcon import MCRcon

from core.config import config
from utils.formatting import replace_color_tag
from utils.logger import logger


class RconClient:
    def __init__(self):
        self.host = config.rcon_host
        self.port = config.rcon_port
        self.password = config.rcon_password

    def _execute_sync(self, command: str) -> str:
        """Synchronous RCON execution in thread pool."""
        try:
            # MCRcon calls signal.signal() in __init__ which fails in non-main
            # threads. Patch it out — we rely on socket timeout instead.
            noop = lambda *a, **kw: None
            with patch.object(signal, "signal", noop):
                with MCRcon(self.host, self.password, self.port) as mcr:
                    mcr.socket.settimeout(5)
                    mcr.connect()
                    response = mcr.command(command)
                    return replace_color_tag(response)
        except ConnectionError as e:
            logger.error(f"RCON connection error: {e}")
            return f"Ошибка подключения к RCON: {e}"
        except Exception as e:
            logger.error(f"RCON error: {e}")
            return f"Ошибка RCON: {e}"

    async def execute(self, command: str) -> str:
        """Async RCON command execution."""
        return await asyncio.to_thread(self._execute_sync, command)

    async def is_available(self) -> bool:
        """Check if RCON server is reachable."""
        try:
            result = await self.execute("list")
            return "error" not in result.lower()
        except Exception:
            return False


rcon = RconClient()
