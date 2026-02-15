from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel

from api.auth import CurrentUser, require_role
from minecraft.rcon import rcon

router = APIRouter(prefix="/api/console", tags=["console"])


class CommandRequest(BaseModel):
    command: str


@router.post("/execute")
async def execute_command(body: CommandRequest, user: Annotated[CurrentUser, require_role("user")]):
    from minecraft.docker_manager import docker_manager
    if not await docker_manager.is_running():
        return {"success": False, "error": "Server is not running"}

    try:
        result = await rcon.execute(body.command)
        response = result or "(empty response)"
        # Truncate long responses
        if len(response) > 4000:
            response = response[:4000] + "..."
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}
