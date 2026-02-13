from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from datetime import datetime, timezone

from db.database import db
from utils.formatting import format_duration, section_header
from utils.nav import check_access, show_menu, back_row

stats_router = Router()

# ── Period presets ───────────────────────────────────────────────
_PERIODS = [
    ("today", "Сегодня", "-1 day"),
    ("7d", "7 дней", "-7 days"),
    ("30d", "30 дней", "-30 days"),
    ("all", "Всё время", ""),
]


def _period_label(suffix: str) -> str:
    for s, label, _ in _PERIODS:
        if s == suffix:
            return label
    return suffix


def _period_since(suffix: str) -> str:
    for s, _, since in _PERIODS:
        if s == suffix:
            return since
    return ""


def _period_buttons(active: str, prefix: str = "st") -> list[list[InlineKeyboardButton]]:
    """Build a row of period filter buttons, highlighting the active one."""
    row = []
    for suffix, label, _ in _PERIODS:
        text = f"• {label} •" if suffix == active else label
        row.append(InlineKeyboardButton(text=text, callback_data=f"{prefix}:period:{suffix}"))
    return [row]


# ── Helpers ──────────────────────────────────────────────────────

def _format_last_seen(dt_str: str) -> str:
    """Relative time string from an ISO timestamp."""
    try:
        dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())
        if secs < 60:
            return "только что"
        if secs < 3600:
            return f"{secs // 60}м назад"
        if secs < 86400:
            return f"{secs // 3600}ч назад"
        return f"{secs // 86400}д назад"
    except (ValueError, TypeError):
        return "—"


def _format_date_short(dt_str: str) -> str:
    """'2025-01-15 10:30' → '15.01'."""
    try:
        return f"{dt_str[8:10]}.{dt_str[5:7]}"
    except (IndexError, TypeError):
        return "?"


def _format_dt_short(dt_str: str) -> str:
    """'2025-01-15 10:30:00' → '15.01 10:30'."""
    try:
        return f"{dt_str[8:10]}.{dt_str[5:7]} {dt_str[11:16]}"
    except (IndexError, TypeError):
        return "?"


def _bar_chart(data: list[tuple[str, int]], max_bars: int = 24) -> str:
    """Build a text histogram.

    data: list of (label, value) pairs.
    Returns multiline string with bars.
    """
    if not data:
        return "  Нет данных"

    data = data[:max_bars]
    max_val = max(v for _, v in data) if data else 1
    if max_val == 0:
        max_val = 1

    lines = []
    bar_width = 12
    for label, val in data:
        filled = round(val / max_val * bar_width)
        bar = "▓" * filled + "░" * (bar_width - filled)
        dur = format_duration(val) if val > 0 else "—"
        lines.append(f"  {label:>5} {bar} {dur}")
    return "\n".join(lines)


def _hour_chart(hourly_data: list) -> str:
    """Build hourly activity chart from DB result (hour, total_secs, count)."""
    # Fill all 24 hours
    by_hour = {h: 0 for h in range(24)}
    for hour, total_secs, _ in hourly_data:
        by_hour[hour] = total_secs

    data = [(f"{h:02d}:00", secs) for h, secs in sorted(by_hour.items())]
    return _bar_chart(data)


def _daily_chart(daily_data: list, max_days: int = 14) -> str:
    """Build daily activity chart from DB result (date, total_secs, count, unique)."""
    if not daily_data:
        return "  Нет данных"

    recent = daily_data[-max_days:]
    data = [(_format_date_short(day), total_secs) for day, total_secs, _, _ in recent]
    return _bar_chart(data)


# ── Main stats menu ─────────────────────────────────────────────

@stats_router.callback_query(F.data == "nav:stats")
async def stats_main(callback: CallbackQuery):
    if not await check_access(callback):
        return
    await _show_stats_overview(callback, "7d")
    await callback.answer()


@stats_router.callback_query(F.data.startswith("st:period:"))
async def stats_period(callback: CallbackQuery):
    if not await check_access(callback):
        return
    period = callback.data.split(":")[2]
    await _show_stats_overview(callback, period)
    await callback.answer()


async def _show_stats_overview(callback: CallbackQuery, period: str):
    """Show main stats overview with top players and summary."""
    since = _period_since(period)
    label = _period_label(period)

    lines = [section_header("📊", f"Статистика — {label}")]

    # Summary
    if since:
        summary = await db.get_period_summary(since)
        if summary:
            unique, total_sess, total_secs = summary
            lines.append(
                f"\n👤 Игроков: <b>{unique}</b>  │  "
                f"📈 Сессий: <b>{total_sess}</b>  │  "
                f"🕐 Всего: <b>{format_duration(total_secs)}</b>"
            )
    else:
        # All time — count from all sessions
        summary = await db.fetch_one(
            """SELECT COUNT(DISTINCT player_name), COUNT(*),
                      COALESCE(SUM(CAST((julianday(COALESCE(left_at, datetime('now')))
                      - julianday(joined_at)) * 86400 AS INTEGER)), 0)
               FROM player_sessions"""
        )
        if summary:
            unique, total_sess, total_secs = summary
            lines.append(
                f"\n👤 Игроков: <b>{unique}</b>  │  "
                f"📈 Сессий: <b>{total_sess}</b>  │  "
                f"🕐 Всего: <b>{format_duration(total_secs)}</b>"
            )

    # Top players
    top = await db.get_top_players(since=since, limit=10)

    if not top:
        lines.append("\nНет данных за этот период.")
    else:
        lines.append("\n<b>🏆 Топ по времени:</b>")
        for i, (name, total_secs, sess_cnt, last_seen, is_online, first_seen) in enumerate(top, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"  {i}.")
            status = "🟢" if is_online else ""
            lines.append(
                f"{medal} {status}<b>{name}</b> — {format_duration(total_secs)} "
                f"({sess_cnt} сесс.)"
            )

    text = "\n".join(lines)

    # Buttons
    buttons = _period_buttons(period)

    # Player buttons for detail
    if top:
        row = []
        for name, *_ in top[:12]:
            row.append(InlineKeyboardButton(
                text=name, callback_data=f"st:player:{period}:{name[:28]}",
            ))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="📈 По часам", callback_data=f"st:hours:{period}"),
        InlineKeyboardButton(text="📅 По дням", callback_data=f"st:days:{period}"),
    ])
    buttons.append([
        InlineKeyboardButton(text="📋 Лог сессий", callback_data=f"st:log:{period}"),
    ])
    buttons.append(back_row("main"))

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, text, kb)


# ── Hourly chart ─────────────────────────────────────────────────

@stats_router.callback_query(F.data.startswith("st:hours:"))
async def stats_hourly(callback: CallbackQuery):
    if not await check_access(callback):
        return
    period = callback.data.split(":")[2]
    since = _period_since(period) or "-365 days"
    label = _period_label(period)

    hourly = await db.get_hourly_activity(since=since)

    lines = [
        section_header("📈", f"Активность по часам — {label}"),
        "\n<pre>",
        _hour_chart(hourly),
        "</pre>",
    ]

    text = "\n".join(lines)
    buttons = _period_buttons(period)
    buttons.append([InlineKeyboardButton(text="◀ К статистике", callback_data=f"st:period:{period}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, text, kb)
    await callback.answer()


# ── Daily chart ──────────────────────────────────────────────────

@stats_router.callback_query(F.data.startswith("st:days:"))
async def stats_daily(callback: CallbackQuery):
    if not await check_access(callback):
        return
    period = callback.data.split(":")[2]
    since = _period_since(period) or "-365 days"
    label = _period_label(period)

    daily = await db.get_daily_activity(since=since)

    lines = [
        section_header("📅", f"Активность по дням — {label}"),
        "\n<pre>",
        _daily_chart(daily),
        "</pre>",
    ]

    # Add daily unique players info
    if daily:
        avg_players = sum(d[3] for d in daily) / len(daily)
        max_players = max(d[3] for d in daily)
        max_day = [d for d in daily if d[3] == max_players][0]
        lines.append(
            f"\n👤 Средн. игроков/день: <b>{avg_players:.1f}</b>"
            f"\n📈 Макс: <b>{max_players}</b> ({_format_date_short(max_day[0])})"
        )

    text = "\n".join(lines)
    buttons = _period_buttons(period)
    buttons.append([InlineKeyboardButton(text="◀ К статистике", callback_data=f"st:period:{period}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, text, kb)
    await callback.answer()


# ── Session log ──────────────────────────────────────────────────

@stats_router.callback_query(F.data.startswith("st:log:"))
async def stats_session_log(callback: CallbackQuery):
    if not await check_access(callback):
        return
    period = callback.data.split(":")[2]
    since = _period_since(period)
    label = _period_label(period)

    sessions = await db.get_session_log(limit=30, since=since)

    if not sessions:
        text = section_header("📋", f"Лог сессий — {label}") + "\n\nНет данных."
    else:
        lines = [section_header("📋", f"Лог сессий — {label}"), ""]
        for name, joined, left in sessions:
            j_short = _format_dt_short(joined)
            if left:
                l_short = left[11:16] if left else "?"
                dur = ""
                try:
                    j_dt = datetime.fromisoformat(joined)
                    l_dt = datetime.fromisoformat(left)
                    secs = int((l_dt - j_dt).total_seconds())
                    dur = f" ({format_duration(secs)})"
                except Exception:
                    pass
                lines.append(f"  {j_short} → {l_short}{dur}  <b>{name}</b>")
            else:
                lines.append(f"  {j_short} → ▶ играет  <b>{name}</b>")
        text = "\n".join(lines)

    buttons = _period_buttons(period)
    buttons.append([InlineKeyboardButton(text="◀ К статистике", callback_data=f"st:period:{period}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, text, kb)
    await callback.answer()


# ── Player detail ────────────────────────────────────────────────

@stats_router.callback_query(F.data.startswith("st:player:"))
async def stats_player_detail(callback: CallbackQuery):
    if not await check_access(callback):
        return

    parts = callback.data.split(":")
    period = parts[2] if len(parts) > 2 else "all"
    pname = ":".join(parts[3:]) if len(parts) > 3 else ""

    if not pname:
        await callback.answer("Имя не указано")
        return

    await _show_player_detail(callback, pname, period)
    await callback.answer()


async def _show_player_detail(callback: CallbackQuery, pname: str, period: str):
    """Show detailed stats for a single player."""
    since = _period_since(period)
    label = _period_label(period)

    pstats = await db.get_player_stats(pname)
    if not pstats:
        text = f"Нет данных по игроку <b>{pname}</b>."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ К статистике", callback_data=f"st:period:{period}")],
        ])
        await show_menu(callback, text, kb)
        return

    status = "🟢 Онлайн" if pstats["online"] else "⚪ Оффлайн"
    avg_secs = pstats["total_seconds"] // max(pstats["session_count"], 1)

    # First seen
    first_seen = await db.get_player_first_seen(pname)
    first_str = _format_date_short(first_seen) if first_seen else "?"

    lines = [
        section_header("👤", pname, status),
        "",
        f"🕐 Общее время: <b>{format_duration(pstats['total_seconds'])}</b>",
        f"📈 Сессий: <b>{pstats['session_count']}</b>",
        f"⏱ Средняя: <b>{format_duration(avg_secs)}</b>",
        f"📅 Первый вход: <b>{first_str}</b>",
        f"📅 Последний: {_format_last_seen(pstats['last_seen'])}",
    ]

    if pstats["online"] and pstats["current_session_start"]:
        start = _format_dt_short(pstats["current_session_start"])
        lines.append(f"▶ Текущая сессия с {start}")

    # Hourly activity for this player
    hourly_since = since or "-365 days"
    hourly = await db.get_hourly_activity(since=hourly_since, player_name=pname)
    if hourly:
        lines.append(f"\n<b>📈 Активность по часам ({label}):</b>")
        lines.append("<pre>")
        lines.append(_hour_chart(hourly))
        lines.append("</pre>")

    # Recent sessions
    sessions = await db.get_player_sessions(pname, limit=10, since=since)
    if sessions:
        lines.append(f"\n<b>📋 Последние сессии:</b>")
        for joined, left, dur in sessions:
            j_short = _format_dt_short(joined)
            if left:
                lines.append(f"  {j_short} — {format_duration(dur)}")
            else:
                lines.append(f"  {j_short} — ▶ играет")

    text = "\n".join(lines)

    buttons = []
    # Sub-views for this player
    buttons.append([
        InlineKeyboardButton(text="📈 По часам", callback_data=f"st:phours:{period}:{pname[:28]}"),
        InlineKeyboardButton(text="📅 По дням", callback_data=f"st:pdays:{period}:{pname[:28]}"),
    ])
    buttons.append([InlineKeyboardButton(text="◀ К статистике", callback_data=f"st:period:{period}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, text, kb)


# ── Player hourly chart ─────────────────────────────────────────

@stats_router.callback_query(F.data.startswith("st:phours:"))
async def stats_player_hourly(callback: CallbackQuery):
    if not await check_access(callback):
        return

    parts = callback.data.split(":")
    period = parts[2] if len(parts) > 2 else "all"
    pname = ":".join(parts[3:]) if len(parts) > 3 else ""

    if not pname:
        await callback.answer("Имя не указано")
        return

    since = _period_since(period) or "-365 days"
    label = _period_label(period)

    hourly = await db.get_hourly_activity(since=since, player_name=pname)

    lines = [
        section_header("📈", f"{pname} — по часам ({label})"),
        "\n<pre>",
        _hour_chart(hourly),
        "</pre>",
    ]

    text = "\n".join(lines)
    buttons = [
        [InlineKeyboardButton(text=f"◀ К {pname}", callback_data=f"st:player:{period}:{pname[:28]}")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, text, kb)
    await callback.answer()


# ── Player daily chart ───────────────────────────────────────────

@stats_router.callback_query(F.data.startswith("st:pdays:"))
async def stats_player_daily(callback: CallbackQuery):
    if not await check_access(callback):
        return

    parts = callback.data.split(":")
    period = parts[2] if len(parts) > 2 else "all"
    pname = ":".join(parts[3:]) if len(parts) > 3 else ""

    if not pname:
        await callback.answer("Имя не указано")
        return

    since = _period_since(period) or "-365 days"
    label = _period_label(period)

    daily = await db.get_daily_activity(since=since, player_name=pname)

    lines = [
        section_header("📅", f"{pname} — по дням ({label})"),
        "\n<pre>",
        _daily_chart(daily),
        "</pre>",
    ]

    if daily:
        total_secs = sum(d[1] for d in daily)
        active_days = len([d for d in daily if d[1] > 0])
        lines.append(
            f"\n📆 Активных дней: <b>{active_days}</b>"
            f"\n🕐 Всего: <b>{format_duration(total_secs)}</b>"
        )
        if active_days > 0:
            avg_per_day = total_secs // active_days
            lines.append(f"⏱ Среднее/день: <b>{format_duration(avg_per_day)}</b>")

    text = "\n".join(lines)
    buttons = [
        [InlineKeyboardButton(text=f"◀ К {pname}", callback_data=f"st:player:{period}:{pname[:28]}")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, text, kb)
    await callback.answer()
