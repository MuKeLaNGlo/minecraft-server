import asyncio
from typing import Annotated

from fastapi import APIRouter

from api.auth import CurrentUser, require_role, get_current_user, Depends
from db.database import db
from minecraft.docker_manager import docker_manager
from minecraft.rcon import rcon
from services.monitoring import monitoring
from utils.logger import logger

router = APIRouter(prefix="/api/server", tags=["server"])


@router.get("/status")
async def server_status():
    running = await docker_manager.is_running()
    result = {"running": running}

    if running:
        status = await docker_manager.status()
        result.update({
            "status": status.get("status", "unknown"),
            "health": status.get("health", "unknown"),
            "started_at": status.get("started_at", ""),
            "cpu_percent": round(status.get("cpu_percent", 0), 1),
            "memory_mb": round(status.get("memory_mb", 0)),
            "memory_limit_mb": round(status.get("memory_limit_mb", 0)),
        })

        tps = await monitoring.get_tps()
        if tps is not None:
            result["tps"] = round(tps, 1)

        from minecraft.player_manager import player_manager
        try:
            players = await player_manager.get_online_players()
            result["players"] = {
                "count": players.get("count", 0),
                "max": players.get("max", 0),
                "list": players.get("players", []),
            }
        except Exception:
            result["players"] = {"count": 0, "max": 0, "list": []}

    return result


@router.post("/start")
async def server_start(user: Annotated[CurrentUser, require_role("admin")]):
    if await docker_manager.is_running():
        return {"success": False, "error": "Server is already running"}
    result = await docker_manager.start()
    logger.info(f"API: Server started by {user.telegram_id}")
    return {"success": True}


@router.post("/stop")
async def server_stop(user: Annotated[CurrentUser, require_role("admin")]):
    if not await docker_manager.is_running():
        return {"success": False, "error": "Server is not running"}
    try:
        await rcon.execute("say Server stopping in 5 seconds!")
        await asyncio.sleep(5)
    except Exception:
        pass
    await db.close_all_sessions()
    result = await docker_manager.stop()
    logger.info(f"API: Server stopped by {user.telegram_id}")
    return {"success": True}


@router.post("/restart")
async def server_restart(user: Annotated[CurrentUser, require_role("admin")]):
    if await docker_manager.is_running():
        try:
            await rcon.execute("save-all")
            await asyncio.sleep(2)
            await rcon.execute("say Server restarting in 5 seconds!")
            await asyncio.sleep(5)
        except Exception:
            pass
    await db.close_all_sessions()
    result = await docker_manager.restart()
    logger.info(f"API: Server restarted by {user.telegram_id}")
    return {"success": True}
