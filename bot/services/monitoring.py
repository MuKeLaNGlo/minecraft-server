import asyncio
import re
from typing import List, Optional

from core.config import config, PLUGIN_LOADERS
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
        """Get TPS from server. Tries multiple commands in priority order."""
        if config.mc_loader in PLUGIN_LOADERS:
            # Paper/Purpur/Spigot — built-in `tps` command
            result = await rcon.execute("tps")
            tps = self._parse_tps_paper(result)
            if tps is not None:
                return tps

        # Vanilla `mspt` command (1.20.1+, works on all loaders)
        result = await rcon.execute("mspt")
        tps = self._parse_mspt(result)
        if tps is not None:
            return tps

        if config.mc_loader not in PLUGIN_LOADERS:
            # Forge/NeoForge — `forge tps`
            result = await rcon.execute("forge tps")
            tps = self._parse_tps(result)
            if tps is not None:
                return tps

        # Last resort — spark plugin/mod
        result = await rcon.execute("spark tps")
        return self._parse_tps_spark(result)

    def _parse_mspt(self, text: str) -> Optional[float]:
        """Parse vanilla/forge mspt output and convert to TPS.

        Format: Server tick times (avg/min/max) from last 5s, 10s, 1m:
                ◴ 0.7/0.3/1.6, 0.6/0.3/1.6, 1.0/0.3/461.1
        We take the 5s average (first number) and compute TPS = min(20, 1000/mspt).
        """
        # Strip color codes
        clean = re.sub(r"\x1b\[[0-9;]*m|§[0-9a-fk-or]", "", text)
        # Find the first group of avg/min/max: e.g. "0.7/0.3/1.6"
        match = re.search(r"([\d.]+)/([\d.]+)/([\d.]+)", clean)
        if match:
            try:
                avg_mspt = float(match.group(1))
                if avg_mspt <= 0:
                    return 20.0
                return min(20.0, round(1000.0 / avg_mspt, 1))
            except (ValueError, ZeroDivisionError):
                pass
        return None

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

    def _parse_tps_paper(self, text: str) -> Optional[float]:
        """Parse Paper/Purpur/Spigot tps output.

        Format: §6TPS from last 1m, 5m, 15m: §a*20.0, §a*20.0, §a*20.0
        Or without color codes: TPS from last 1m, 5m, 15m: *20.0, *20.0, *20.0
        We take the 1-minute TPS (first value).
        """
        # Strip Minecraft color codes §X
        clean = re.sub(r"§[0-9a-fk-or]", "", text)
        # Find all TPS values (may have * prefix for "capped at 20")
        match = re.search(r"TPS.*?:\s*\*?([\d.]+)", clean)
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
