from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel

from api.auth import CurrentUser, require_role
from minecraft.world_manager import world_manager

router = APIRouter(prefix="/api/worlds", tags=["worlds"])


class WorldCreate(BaseModel):
    name: str


class WorldRename(BaseModel):
    new_name: str


class WorldClone(BaseModel):
    clone_name: str


@router.get("")
async def list_worlds(user: Annotated[CurrentUser, require_role("admin")]):
    worlds = await world_manager.list_worlds()
    current = await world_manager.get_current_world()
    return {
        "current": current,
        "worlds": [
            {
                "name": w["name"],
                "size_mb": round(w["size_mb"], 1),
                "last_modified": w["last_modified"].isoformat(),
                "generated": w["generated"],
                "dimensions": w["dimensions"],
                "active": w["name"] == current,
            }
            for w in worlds
        ],
    }


@router.post("")
async def create_world(body: WorldCreate, user: Annotated[CurrentUser, require_role("admin")]):
    return await world_manager.create_world(body.name)


@router.post("/{name}/switch")
async def switch_world(name: str, user: Annotated[CurrentUser, require_role("admin")]):
    return await world_manager.switch_world(name)


@router.put("/{name}")
async def rename_world(name: str, body: WorldRename, user: Annotated[CurrentUser, require_role("admin")]):
    return await world_manager.rename_world(name, body.new_name)


@router.post("/{name}/clone")
async def clone_world(name: str, body: WorldClone, user: Annotated[CurrentUser, require_role("admin")]):
    return await world_manager.clone_world(name, body.clone_name)


@router.delete("/{name}")
async def delete_world(name: str, user: Annotated[CurrentUser, require_role("admin")]):
    return await world_manager.delete_world(name)
