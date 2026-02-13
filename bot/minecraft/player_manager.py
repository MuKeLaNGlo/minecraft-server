import re
from typing import Dict, List, Optional

from minecraft.rcon import rcon

_VALID_USERNAME = re.compile(r"^[a-zA-Z0-9_]{1,16}$")


def _validate_player(name: str) -> str | None:
    """Return error message if player name is invalid, None if OK."""
    if not name or not _VALID_USERNAME.match(name):
        return f"Недопустимый ник: {name!r}. Допустимы буквы, цифры, _ (1-16 символов)."
    return None


class PlayerManager:
    async def get_online_players(self) -> Dict:
        """Parse /list output. Returns {count, max, players}."""
        result = await rcon.execute("list")
        # Format: "There are X of a max of Y players online: player1, player2"
        match = re.search(
            r"There are (\d+) of a max of (\d+) players online:(.*)",
            result,
            re.IGNORECASE,
        )
        if match:
            count = int(match.group(1))
            max_players = int(match.group(2))
            players_str = match.group(3).strip()
            players = (
                [p.strip() for p in players_str.split(",") if p.strip()]
                if players_str
                else []
            )
            return {"count": count, "max": max_players, "players": players}

        return {"count": 0, "max": 0, "players": [], "raw": result}

    async def kick(self, player: str, reason: str = "") -> str:
        if err := _validate_player(player):
            return err
        cmd = f"kick {player}" + (f" {reason}" if reason else "")
        return await rcon.execute(cmd)

    async def ban(self, player: str, reason: str = "") -> str:
        if err := _validate_player(player):
            return err
        cmd = f"ban {player}" + (f" {reason}" if reason else "")
        return await rcon.execute(cmd)

    async def pardon(self, player: str) -> str:
        if err := _validate_player(player):
            return err
        return await rcon.execute(f"pardon {player}")

    async def whitelist_add(self, player: str) -> str:
        if err := _validate_player(player):
            return err
        return await rcon.execute(f"whitelist add {player}")

    async def whitelist_remove(self, player: str) -> str:
        if err := _validate_player(player):
            return err
        return await rcon.execute(f"whitelist remove {player}")

    async def whitelist_list(self) -> str:
        return await rcon.execute("whitelist list")

    async def op(self, player: str) -> str:
        if err := _validate_player(player):
            return err
        return await rcon.execute(f"op {player}")

    async def deop(self, player: str) -> str:
        if err := _validate_player(player):
            return err
        return await rcon.execute(f"deop {player}")

    async def gamemode(self, player: str, mode: str) -> str:
        if err := _validate_player(player):
            return err
        return await rcon.execute(f"gamemode {mode} {player}")

    async def teleport(self, player: str, target: str) -> str:
        return await rcon.execute(f"tp {player} {target}")

    async def say(self, text: str) -> str:
        return await rcon.execute(f"say {text}")

    async def tellraw(self, target: str, json_text: str) -> str:
        return await rcon.execute(f'tellraw {target} {json_text}')

    async def banlist(self) -> str:
        return await rcon.execute("banlist")


player_manager = PlayerManager()
