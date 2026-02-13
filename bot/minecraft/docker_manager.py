import asyncio
from datetime import datetime
from typing import Optional

import docker

from core.config import config
from utils.logger import logger


def _calc_cpu_percent(stats: dict) -> float:
    """Calculate CPU usage percentage from docker stats."""
    try:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        num_cpus = stats["cpu_stats"]["online_cpus"]
        if system_delta > 0 and cpu_delta >= 0:
            return (cpu_delta / system_delta) * num_cpus * 100.0
    except (KeyError, ZeroDivisionError):
        pass
    return 0.0


class DockerManager:
    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._container_name = config.mc_container_name

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def _get_container(self):
        return self.client.containers.get(self._container_name)

    async def start(self) -> str:
        def _start():
            try:
                container = self._get_container()
                if container.status == "running":
                    return "Сервер уже запущен."
                container.start()
                return "Сервер запускается..."
            except docker.errors.NotFound:
                return "Контейнер не найден."
            except Exception as e:
                logger.error(f"Docker start error: {e}")
                return f"Ошибка запуска: {e}"

        return await asyncio.to_thread(_start)

    async def stop(self) -> str:
        def _stop():
            try:
                container = self._get_container()
                if container.status != "running":
                    return "Сервер уже остановлен."
                container.stop(timeout=30)
                return "Сервер остановлен."
            except docker.errors.NotFound:
                return "Контейнер не найден."
            except Exception as e:
                logger.error(f"Docker stop error: {e}")
                return f"Ошибка остановки: {e}"

        return await asyncio.to_thread(_stop)

    async def restart(self) -> str:
        def _restart():
            try:
                container = self._get_container()
                container.restart(timeout=30)
                return "Сервер перезапущен."
            except docker.errors.NotFound:
                return "Контейнер не найден."
            except Exception as e:
                logger.error(f"Docker restart error: {e}")
                return f"Ошибка перезапуска: {e}"

        return await asyncio.to_thread(_restart)

    async def status(self) -> dict:
        def _status():
            try:
                container = self._get_container()
                stats = container.stats(stream=False)
                return {
                    "status": container.status,
                    "health": container.attrs.get("State", {})
                    .get("Health", {})
                    .get("Status", "unknown"),
                    "started_at": container.attrs.get("State", {}).get(
                        "StartedAt", ""
                    ),
                    "cpu_percent": _calc_cpu_percent(stats),
                    "memory_mb": stats.get("memory_stats", {}).get("usage", 0)
                    / 1024
                    / 1024,
                    "memory_limit_mb": stats.get("memory_stats", {}).get("limit", 0)
                    / 1024
                    / 1024,
                }
            except docker.errors.NotFound:
                return {"status": "not_found", "health": "unknown"}
            except Exception as e:
                logger.error(f"Docker status error: {e}")
                return {"status": "error", "health": str(e)}

        return await asyncio.to_thread(_status)

    async def logs(self, lines: int = 50) -> str:
        def _logs():
            try:
                container = self._get_container()
                return container.logs(tail=lines).decode("utf-8", errors="replace")
            except docker.errors.NotFound:
                return "Контейнер не найден."
            except Exception as e:
                logger.error(f"Docker logs error: {e}")
                return f"Ошибка получения логов: {e}"

        return await asyncio.to_thread(_logs)

    async def logs_since(self, since: datetime) -> str:
        """Get container logs since a specific timestamp."""
        def _logs():
            try:
                container = self._get_container()
                return container.logs(
                    since=since, timestamps=True, follow=False
                ).decode("utf-8", errors="replace")
            except docker.errors.NotFound:
                return ""
            except Exception as e:
                logger.error(f"Docker logs_since error: {e}")
                return ""

        return await asyncio.to_thread(_logs)

    async def is_running(self) -> bool:
        def _check():
            try:
                container = self._get_container()
                return container.status == "running"
            except Exception:
                return False

        return await asyncio.to_thread(_check)


docker_manager = DockerManager()
