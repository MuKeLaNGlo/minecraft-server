import asyncio
import re
from typing import List, Optional

from core.config import config
from minecraft.docker_manager import docker_manager
from minecraft.rcon import rcon
from utils.logger import logger


class MonitoringService:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, bot, alert_chat_ids: List[str], interval: int = 60):
        """Start periodic monitoring loop."""
        self._running = True
        self._bot = bot
        self._alert_chat_ids = alert_chat_ids
        self._interval = interval
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Monitoring started (interval={interval}s)")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring stopped")

    async def _loop(self):
        while self._running:
            try:
                await self._check()
            except Exception as e:
                logger.warning(f"Monitoring check error: {e}")
            await asyncio.sleep(self._interval)

    async def _check(self):
        if not await docker_manager.is_running():
            return

        # TPS check
        tps = await self.get_tps()
        if tps is not None and tps < 15.0:
            await self._alert(f"TPS низкий: {tps:.1f}")

        # RAM check
        status = await docker_manager.status()
        mem_mb = status.get("memory_mb", 0)
        limit_mb = status.get("memory_limit_mb", 0)
        if limit_mb > 0:
            pct = (mem_mb / limit_mb) * 100
            if pct > 90:
                await self._alert(
                    f"RAM: {pct:.0f}% ({mem_mb:.0f}/{limit_mb:.0f} МБ)"
                )

    async def get_tps(self) -> Optional[float]:
        """Get TPS from server. Tries forge tps, then spark."""
        result = await rcon.execute("forge tps")
        tps = self._parse_tps(result)
        if tps is not None:
            return tps

        # Try spark if forge didn't work
        result = await rcon.execute("spark tps")
        return self._parse_tps_spark(result)

    def _parse_tps(self, text: str) -> Optional[float]:
        """Parse forge tps output."""
        # "Overall: Mean tick time: 12.34 ms. Mean TPS: 20.00"
        match = re.search(r"Mean TPS:\s*([\d.]+)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    def _parse_tps_spark(self, text: str) -> Optional[float]:
        """Parse spark tps output."""
        # Various formats, try to find a number after TPS
        match = re.search(r"TPS.*?([\d.]+)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    async def get_status_text(self) -> str:
        """Get full status text for display."""
        lines = []

        # Server status
        running = await docker_manager.is_running()
        lines.append(f"Сервер: {'🟢 запущен' if running else '🔴 остановлен'}")

        if not running:
            return "\n".join(lines)

        # TPS
        tps = await self.get_tps()
        if tps is not None:
            tps_emoji = "🟢" if tps >= 18 else "🟡" if tps >= 15 else "🔴"
            lines.append(f"TPS: {tps_emoji} {tps:.1f}")

        # Players
        from minecraft.player_manager import player_manager
        data = await player_manager.get_online_players()
        lines.append(f"Игроки: {data.get('count', 0)}/{data.get('max', 0)}")
        if data.get("players"):
            lines.append("  " + ", ".join(data["players"]))

        # Resources
        status = await docker_manager.status()
        cpu = status.get("cpu_percent", 0)
        mem_mb = status.get("memory_mb", 0)
        limit_mb = status.get("memory_limit_mb", 0)
        mem_pct = (mem_mb / limit_mb * 100) if limit_mb > 0 else 0

        lines.append(f"CPU: {cpu:.1f}%")
        lines.append(f"RAM: {mem_mb:.0f}/{limit_mb:.0f} МБ ({mem_pct:.0f}%)")

        # Uptime
        started = status.get("started_at", "")
        if started:
            lines.append(f"Запущен: {started[:19].replace('T', ' ')}")

        # Config
        lines.append(f"\nВерсия: {config.mc_version}")
        lines.append(f"Лоадер: {config.mc_type} ({config.mc_loader})")
        lines.append(f"Память: {config.mc_memory}")

        return "\n".join(lines)

    async def _alert(self, text: str):
        for chat_id in self._alert_chat_ids:
            try:
                await self._bot.send_message(
                    chat_id, f"⚠ <b>Предупреждение:</b> {text}"
                )
            except Exception:
                pass


monitoring = MonitoringService()
