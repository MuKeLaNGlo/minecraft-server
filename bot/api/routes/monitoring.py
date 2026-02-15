import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from minecraft.docker_manager import docker_manager
from services.monitoring import monitoring

router = APIRouter(tags=["monitoring"])


@router.get("/api/monitoring")
async def get_monitoring():
    running = await docker_manager.is_running()
    if not running:
        return {"running": False}

    status = await docker_manager.status()
    tps = await monitoring.get_tps()

    from minecraft.player_manager import player_manager
    try:
        players = await player_manager.get_online_players()
        player_count = players.get("count", 0)
        player_list = players.get("players", [])
    except Exception:
        player_count = 0
        player_list = []

    return {
        "running": True,
        "tps": round(tps, 1) if tps else None,
        "cpu_percent": round(status.get("cpu_percent", 0), 1),
        "memory_mb": round(status.get("memory_mb", 0)),
        "memory_limit_mb": round(status.get("memory_limit_mb", 0)),
        "players_online": player_count,
        "players": player_list,
    }


@router.websocket("/ws/monitoring")
async def ws_monitoring(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            running = await docker_manager.is_running()
            if not running:
                await websocket.send_json({"running": False})
                await asyncio.sleep(2)
                continue

            status = await docker_manager.status()
            tps = await monitoring.get_tps()

            from minecraft.player_manager import player_manager
            try:
                players = await player_manager.get_online_players()
                player_count = players.get("count", 0)
                player_list = players.get("players", [])
            except Exception:
                player_count = 0
                player_list = []

            await websocket.send_json({
                "running": True,
                "tps": round(tps, 1) if tps else None,
                "cpu_percent": round(status.get("cpu_percent", 0), 1),
                "memory_mb": round(status.get("memory_mb", 0)),
                "memory_limit_mb": round(status.get("memory_limit_mb", 0)),
                "players_online": player_count,
                "players": player_list,
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
