import re
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel

from api.auth import CurrentUser, require_role
from minecraft.player_manager import player_manager
from minecraft.rcon import rcon

router = APIRouter(prefix="/api/players", tags=["players"])


class PlayerAction(BaseModel):
    reason: str = ""


class GamemodeAction(BaseModel):
    mode: str  # survival, creative, adventure, spectator


class RconCommand(BaseModel):
    command: str


@router.get("/online")
async def online_players():
    try:
        data = await player_manager.get_online_players()
        return {
            "count": data.get("count", 0),
            "max": data.get("max", 0),
            "players": data.get("players", []),
        }
    except Exception:
        return {"count": 0, "max": 0, "players": []}


@router.post("/{name}/kick")
async def kick_player(name: str, body: PlayerAction, user: Annotated[CurrentUser, require_role("admin")]):
    result = await player_manager.kick(name, body.reason)
    return {"success": True, "response": result}


@router.post("/{name}/ban")
async def ban_player(name: str, body: PlayerAction, user: Annotated[CurrentUser, require_role("admin")]):
    result = await player_manager.ban(name, body.reason)
    return {"success": True, "response": result}


@router.post("/{name}/pardon")
async def pardon_player(name: str, user: Annotated[CurrentUser, require_role("admin")]):
    result = await player_manager.pardon(name)
    return {"success": True, "response": result}


@router.post("/{name}/op")
async def op_player(name: str, user: Annotated[CurrentUser, require_role("admin")]):
    result = await player_manager.op(name)
    return {"success": True, "response": result}


@router.post("/{name}/deop")
async def deop_player(name: str, user: Annotated[CurrentUser, require_role("admin")]):
    result = await player_manager.deop(name)
    return {"success": True, "response": result}


@router.post("/{name}/gamemode")
async def gamemode_player(name: str, body: GamemodeAction, user: Annotated[CurrentUser, require_role("admin")]):
    if body.mode not in ("survival", "creative", "adventure", "spectator"):
        return {"success": False, "error": "Invalid gamemode"}
    result = await player_manager.gamemode(name, body.mode)
    return {"success": True, "response": result}


@router.post("/{name}/whitelist/add")
async def whitelist_add(name: str, user: Annotated[CurrentUser, require_role("admin")]):
    result = await player_manager.whitelist_add(name)
    return {"success": True, "response": result}


@router.post("/{name}/whitelist/remove")
async def whitelist_remove(name: str, user: Annotated[CurrentUser, require_role("admin")]):
    result = await player_manager.whitelist_remove(name)
    return {"success": True, "response": result}


@router.get("/{name}/live")
async def player_live_data(name: str, user: Annotated[CurrentUser, require_role("user")]):
    """Get live data for an online player: XP level, health, position, dimension, gamemode."""
    data: dict = {"online": False}
    try:
        # XP Level
        raw = await rcon.execute(f"data get entity {name} XpLevel")
        m = re.search(r"XpLevel.*?(-?\d+)", raw)
        if m:
            data["online"] = True
            data["xp_level"] = int(m.group(1))
        else:
            # Player might be offline
            if "No entity" in raw or "not found" in raw.lower():
                return data

        # Health
        raw = await rcon.execute(f"data get entity {name} Health")
        m = re.search(r"Health.*?(-?[\d.]+)", raw)
        if m:
            data["health"] = round(float(m.group(1)), 1)

        # Position
        raw = await rcon.execute(f"data get entity {name} Pos")
        m = re.search(r"\[(-?[\d.]+)d,\s*(-?[\d.]+)d,\s*(-?[\d.]+)d\]", raw)
        if m:
            data["pos"] = {
                "x": round(float(m.group(1))),
                "y": round(float(m.group(2))),
                "z": round(float(m.group(3))),
            }

        # Dimension
        raw = await rcon.execute(f"data get entity {name} Dimension")
        m = re.search(r'"(minecraft:\w+)"', raw)
        if m:
            dim = m.group(1).replace("minecraft:", "")
            data["dimension"] = dim

        # Gamemode (playerGameType: 0=surv, 1=creat, 2=adv, 3=spec)
        raw = await rcon.execute(f"data get entity {name} playerGameType")
        m = re.search(r"playerGameType.*?(\d+)", raw)
        if m:
            gm_map = {0: "survival", 1: "creative", 2: "adventure", 3: "spectator"}
            data["gamemode"] = gm_map.get(int(m.group(1)), "unknown")

        # Food level
        raw = await rcon.execute(f"data get entity {name} foodLevel")
        m = re.search(r"foodLevel.*?(\d+)", raw)
        if m:
            data["food_level"] = int(m.group(1))

    except Exception:
        pass

    return data


@router.post("/{name}/rcon")
async def player_rcon(name: str, body: RconCommand, user: Annotated[CurrentUser, require_role("admin")]):
    """Execute an RCON command with {player} replaced by this player's name."""
    cmd = body.command.replace("{player}", name)
    result = await rcon.execute(cmd)
    return {"success": True, "response": result or "(пусто)"}
