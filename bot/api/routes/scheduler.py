from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel

from api.auth import CurrentUser, require_role
from db.database import db
from services.scheduler import add_task, remove_task, toggle_task

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class TaskCreate(BaseModel):
    task_type: str  # "backup", "restart", "command"
    cron: str
    extra_data: str = ""


@router.get("/tasks")
async def list_tasks(user: Annotated[CurrentUser, require_role("admin")]):
    rows = await db.get_scheduled_tasks()
    return [
        {
            "id": r[0],
            "type": r[1],
            "cron": r[2],
            "enabled": bool(r[3]),
            "extra_data": r[4] or "",
            "created_at": r[5],
        }
        for r in rows
    ]


@router.post("/tasks")
async def create_task(body: TaskCreate, user: Annotated[CurrentUser, require_role("admin")]):
    if body.task_type not in ("backup", "restart", "command"):
        return {"success": False, "error": "Invalid task type"}
    task_id = await add_task(body.task_type, body.cron, body.extra_data or None)
    return {"success": True, "id": task_id}


@router.post("/tasks/{task_id}/toggle")
async def toggle_task_endpoint(task_id: int, user: Annotated[CurrentUser, require_role("admin")]):
    rows = await db.get_scheduled_tasks()
    task = next((r for r in rows if r[0] == task_id), None)
    if not task:
        return {"success": False, "error": "Task not found"}
    new_state = not bool(task[3])
    await toggle_task(task_id, new_state)
    return {"success": True, "enabled": new_state}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user: Annotated[CurrentUser, require_role("admin")]):
    await remove_task(task_id)
    return {"success": True}
