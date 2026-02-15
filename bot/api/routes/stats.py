from typing import Annotated

from fastapi import APIRouter, Query

from api.auth import CurrentUser, require_role
from db.database import db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def stats_overview(
    period: str = Query("7d", regex="^(today|7d|30d|all)$"),
):
    since = {"today": "-1 day", "7d": "-7 days", "30d": "-30 days", "all": "-100 years"}.get(period, "-7 days")

    summary = await db.get_period_summary(since)
    unique, sessions, total_secs = summary if summary else (0, 0, 0)

    return {
        "period": period,
        "unique_players": unique or 0,
        "total_sessions": sessions or 0,
        "total_hours": round((total_secs or 0) / 3600, 1),
    }


@router.get("/top")
async def stats_top(
    period: str = Query("7d", regex="^(today|7d|30d|all)$"),
    limit: int = Query(10, ge=1, le=50),
):
    since = {"today": "-1 day", "7d": "-7 days", "30d": "-30 days", "all": "-100 years"}.get(period, "-7 days")
    rows = await db.get_top_players(since=since, limit=limit)

    return [
        {
            "name": r[0],
            "total_seconds": r[1] or 0,
            "total_hours": round((r[1] or 0) / 3600, 1),
            "sessions": r[2] or 0,
            "last_seen": r[3],
            "online": bool(r[4]),
            "first_seen": r[5],
        }
        for r in rows
    ]


@router.get("/activity/hourly")
async def stats_hourly(
    period: str = Query("7d", regex="^(today|7d|30d|all)$"),
    player: str = Query(""),
):
    since = {"today": "-1 day", "7d": "-7 days", "30d": "-30 days", "all": "-90 days"}.get(period, "-7 days")
    rows = await db.get_hourly_activity(since=since, player_name=player)

    # Fill all 24 hours
    data = {h: {"hour": h, "minutes": 0, "sessions": 0} for h in range(24)}
    for hour, secs, count in rows:
        data[hour] = {"hour": hour, "minutes": round((secs or 0) / 60), "sessions": count or 0}

    return list(data.values())


@router.get("/activity/daily")
async def stats_daily(
    period: str = Query("30d", regex="^(7d|30d|all)$"),
    player: str = Query(""),
):
    since = {"7d": "-7 days", "30d": "-30 days", "all": "-90 days"}.get(period, "-30 days")
    rows = await db.get_daily_activity(since=since, player_name=player)

    return [
        {
            "date": r[0],
            "hours": round((r[1] or 0) / 3600, 1),
            "sessions": r[2] or 0,
            "unique_players": r[3] or 0,
        }
        for r in rows
    ]


@router.get("/player/{name}")
async def stats_player(name: str):
    stats = await db.get_player_stats(name)
    if not stats:
        return {"found": False}

    first_seen = await db.get_player_first_seen(name)
    sessions = await db.get_player_sessions(name, limit=20)

    return {
        "found": True,
        "name": name,
        "session_count": stats["session_count"],
        "total_hours": round(stats["total_seconds"] / 3600, 1),
        "total_seconds": stats["total_seconds"],
        "last_seen": stats["last_seen"],
        "online": stats["online"],
        "first_seen": first_seen,
        "recent_sessions": [
            {
                "joined": s[0],
                "left": s[1],
                "duration_seconds": s[2] or 0,
            }
            for s in sessions
        ],
    }


@router.get("/sessions")
async def stats_sessions(limit: int = Query(30, ge=1, le=100)):
    rows = await db.get_session_log(limit=limit)
    return [
        {"player": r[0], "joined": r[1], "left": r[2]}
        for r in rows
    ]
