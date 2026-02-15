import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from minecraft.docker_manager import docker_manager
from utils.formatting import clean_log
from api.auth import CurrentUser, require_role

router = APIRouter(tags=["logs"])

MAX_INITIAL_LINES = 200
POLL_INTERVAL = 1.0


def _split_lines(raw: str) -> list[str]:
    """Clean raw docker logs and split into non-empty lines."""
    cleaned = clean_log(raw)
    return [ln for ln in cleaned.splitlines() if ln.strip()]


@router.get("/api/logs/history")
async def logs_history(
    lines: int = Query(default=500, ge=50, le=5000),
    _user: Annotated[CurrentUser, require_role("admin")] = None,
):
    """Return last N log lines (for loading older history)."""
    running = await docker_manager.is_running()
    if not running:
        return {"lines": []}
    raw = await docker_manager.logs(lines=lines)
    return {"lines": _split_lines(raw)}


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        # Send initial batch of recent logs
        running = await docker_manager.is_running()
        if running:
            raw = await docker_manager.logs(lines=MAX_INITIAL_LINES)
            lines = _split_lines(raw)
            await websocket.send_json({"type": "initial", "lines": lines})
        else:
            await websocket.send_json({"type": "initial", "lines": []})

        last_poll = datetime.now(timezone.utc)

        # Stream new lines
        while True:
            await asyncio.sleep(POLL_INTERVAL)

            running = await docker_manager.is_running()
            if not running:
                await asyncio.sleep(3)
                continue

            now = datetime.now(timezone.utc)
            raw = await docker_manager.logs_since(last_poll)
            last_poll = now

            if not raw or not raw.strip():
                continue

            # Docker logs_since returns timestamped lines
            # Strip Docker timestamp prefix (first 31 chars)
            content_lines = []
            for line in raw.strip().splitlines():
                content = line
                if len(line) > 31 and line[0].isdigit():
                    content = line[31:].strip() if " " in line[:35] else line
                if content.strip():
                    content_lines.append(content)

            if not content_lines:
                continue

            cleaned = clean_log("\n".join(content_lines))
            new_lines = [ln for ln in cleaned.splitlines() if ln.strip()]

            if new_lines:
                await websocket.send_json({"type": "new", "lines": new_lines})

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
