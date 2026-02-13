from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import config
from minecraft.docker_manager import docker_manager
from services.monitoring import monitoring
from utils.formatting import (
    section_header, progress_bar, status_dot,
)
from utils.nav import show_menu, back_row

monitoring_router = Router()

MONITORING_MENU_TEXT = section_header(
    "📊", "Мониторинг",
    "Статус сервера, TPS, ресурсы и игроки в реальном времени.",
)

_monitoring_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="mon:refresh")],
        back_row("main"),
    ]
)


async def _build_status_text() -> str:
    """Build rich monitoring text with progress bars."""
    running = await docker_manager.is_running()
    lines = [f"Сервер: {'🟢 запущен' if running else '🔴 остановлен'}"]

    if not running:
        return "\n".join(lines)

    # TPS
    tps = await monitoring.get_tps()
    if tps is not None:
        tps_pct = min(tps / 20.0 * 100, 100)
        lines.append(f"\nTPS: {status_dot(100 - tps_pct)} {progress_bar(tps, 20)} {tps:.1f}/20")

    # Players
    from minecraft.player_manager import player_manager
    data = await player_manager.get_online_players()
    count, max_p = data.get("count", 0), data.get("max", 0)
    lines.append(f"Игроки: {count}/{max_p}")
    if data.get("players"):
        lines.append("  " + ", ".join(data["players"]))

    # Resources
    status = await docker_manager.status()
    cpu = status.get("cpu_percent", 0)
    mem_mb = status.get("memory_mb", 0)
    limit_mb = status.get("memory_limit_mb", 0)
    mem_pct = (mem_mb / limit_mb * 100) if limit_mb > 0 else 0

    lines.append(f"\nCPU: {status_dot(cpu)} {progress_bar(cpu, 100)} {cpu:.1f}%")
    lines.append(
        f"RAM: {status_dot(mem_pct)} {progress_bar(mem_mb, limit_mb)} "
        f"{mem_mb:.0f}/{limit_mb:.0f} МБ"
    )

    # Uptime
    started = status.get("started_at", "")
    if started:
        lines.append(f"\nЗапущен: {started[:19].replace('T', ' ')}")

    # Config
    lines.append(f"\nВерсия: {config.mc_version}")
    lines.append(f"Лоадер: {config.mc_type} ({config.mc_loader})")
    lines.append(f"Память: {config.mc_memory}")

    return "\n".join(lines)


@monitoring_router.callback_query(F.data == "nav:monitoring")
async def monitoring_menu(callback: CallbackQuery):
    await callback.answer()
    text = await _build_status_text()
    full_text = f"{MONITORING_MENU_TEXT}\n\n{text}"
    await show_menu(callback, full_text, _monitoring_kb)


@monitoring_router.callback_query(F.data == "mon:refresh")
async def monitoring_refresh(callback: CallbackQuery):
    await callback.answer("Обновляю...")
    text = await _build_status_text()
    full_text = f"{MONITORING_MENU_TEXT}\n\n{text}"
    await show_menu(callback, full_text, _monitoring_kb)
