import asyncio
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from db.database import db
from minecraft.docker_manager import docker_manager
from minecraft.player_manager import player_manager
from minecraft.rcon import rcon
from states.states import ServerState
from utils.formatting import truncate, progress_bar, status_dot, clean_log, success_text, format_duration, LINE
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

server_router = Router()

# Active auto-refresh tasks per message id
_refresh_tasks: dict[int, asyncio.Task] = {}
_REFRESH_INTERVAL = 3  # seconds
_REFRESH_MAX = 60  # max refreshes (~3 min), then stop


def _format_uptime(started_at: str) -> str:
    """Compute uptime from Docker started_at ISO timestamp."""
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - started
        total_secs = int(delta.total_seconds())
        if total_secs < 60:
            return f"{total_secs} сек"
        days = total_secs // 86400
        hours = (total_secs % 86400) // 3600
        minutes = (total_secs % 3600) // 60
        if days > 0:
            return f"{days}д {hours}ч {minutes}м"
        if hours > 0:
            return f"{hours}ч {minutes}м"
        return f"{minutes}м"
    except (ValueError, TypeError):
        return "—"


async def _build_status_text() -> str:
    """Build server status text with docker stats and online players."""
    status = await docker_manager.status()

    if status.get("status") == "not_found":
        return f"{LINE}\n🖥 <b>Сервер</b>\n{LINE}\n\n⚫ Контейнер не найден"

    if status.get("status") == "error":
        return f"{LINE}\n🖥 <b>Сервер</b>\n{LINE}\n\n🔴 Ошибка: {status.get('health')}"

    state = status["status"]
    health = status["health"]

    if state != "running":
        return f"{LINE}\n🖥 <b>Сервер</b>\n{LINE}\n\n⚫ Остановлен"

    mem_mb = status.get("memory_mb", 0)
    limit_mb = status.get("memory_limit_mb", 0)
    mem_pct = (mem_mb / limit_mb * 100) if limit_mb > 0 else 0
    cpu_raw = status.get("cpu_percent", 0)  # docker-style: 100% = 1 core
    online_cpus = status.get("online_cpus", 1) or 1
    cpu = cpu_raw / online_cpus  # normalize to 0-100%
    started_at = status.get("started_at", "")
    uptime = _format_uptime(started_at) if started_at else "—"

    # Health indicator
    if health == "healthy":
        health_icon = "🟢"
        health_text = "Работает"
    elif health == "starting":
        health_icon = "🟡"
        health_text = "Запускается..."
    else:
        health_icon = "🔴"
        health_text = health

    lines = [
        f"{LINE}",
        f"🖥 <b>Сервер</b> — {health_icon} {health_text}",
        f"{LINE}",
        "",
        f"CPU: {status_dot(cpu)} {progress_bar(cpu, 100)} {cpu:.1f}% ({online_cpus} ядер)",
        f"RAM: {status_dot(mem_pct)} {progress_bar(mem_mb, limit_mb)} {mem_mb:.0f}/{limit_mb:.0f} МБ",
        f"⏱ Аптайм: <b>{uptime}</b>",
    ]

    # Online players (only if healthy — RCON available)
    if health == "healthy":
        try:
            data = await player_manager.get_online_players()
            count = data.get("count", 0)
            max_p = data.get("max", 0)
            players = data.get("players", [])
            if players:
                names = ", ".join(f"<b>{p}</b>" for p in players)
                lines.append(f"\n👥 Онлайн ({count}/{max_p}): {names}")
            else:
                lines.append(f"\n👥 Онлайн: 0/{max_p}")
        except Exception:
            pass

    return "\n".join(lines)


_server_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="▶ Старт", callback_data="srv:start"),
            InlineKeyboardButton(text="⏹ Стоп", callback_data="srv:stop"),
        ],
        [
            InlineKeyboardButton(text="🔄 Рестарт", callback_data="srv:restart"),
        ],
        [
            InlineKeyboardButton(text="📋 Логи (50)", callback_data="srv:logs:50"),
            InlineKeyboardButton(text="📋 Логи (200)", callback_data="srv:logs:200"),
        ],
        [
            InlineKeyboardButton(text="🔒 Пароль", callback_data="srv:password"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="srv:refresh"),
        ],
        back_row("main"),
    ]
)


def _stop_refresh(msg_id: int) -> None:
    """Cancel auto-refresh task for a message."""
    task = _refresh_tasks.pop(msg_id, None)
    if task and not task.done():
        task.cancel()


async def _auto_refresh(message, msg_id: int) -> None:
    """Background task: update server status message periodically."""
    try:
        for _ in range(_REFRESH_MAX):
            await asyncio.sleep(_REFRESH_INTERVAL)
            text = await _build_status_text()
            try:
                await message.edit_text(text, reply_markup=_server_kb, parse_mode="HTML")
            except Exception:
                # Message deleted, user navigated away, or content unchanged
                break
    except asyncio.CancelledError:
        pass
    finally:
        _refresh_tasks.pop(msg_id, None)


async def _show_server_menu(callback_or_msg, start_refresh: bool = True):
    """Show server status and optionally start auto-refresh."""
    text = await _build_status_text()

    if isinstance(callback_or_msg, CallbackQuery):
        msg = callback_or_msg.message
        try:
            await msg.edit_text(text, reply_markup=_server_kb, parse_mode="HTML")
        except Exception:
            msg = await msg.answer(text, reply_markup=_server_kb, parse_mode="HTML")
    else:
        msg = await callback_or_msg.answer(text, reply_markup=_server_kb, parse_mode="HTML")

    if start_refresh and msg:
        _stop_refresh(msg.message_id)
        task = asyncio.create_task(_auto_refresh(msg, msg.message_id))
        _refresh_tasks[msg.message_id] = task


@server_router.callback_query(F.data == "nav:server")
async def server_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    # Stop any previous refresh for this message
    _stop_refresh(callback.message.message_id)
    await _show_server_menu(callback)
    await callback.answer()


@server_router.callback_query(F.data.startswith("srv:"))
async def server_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "refresh":
        # Manual refresh — restart auto-refresh cycle
        _stop_refresh(callback.message.message_id)
        await _show_server_menu(callback)
        await callback.answer()
        return

    if action == "password":
        _stop_refresh(callback.message.message_id)
        await callback.answer()
        password = await db.get_setting("server_password", "")
        if password:
            text = f"🔒 <b>Пароль сервера</b>\n\nТекущий пароль: <code>{password}</code>"
        else:
            text = "🔒 <b>Пароль сервера</b>\n\nПароль не установлен."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏ Установить пароль", callback_data="srv:set_password")],
            *([[InlineKeyboardButton(text="🗑 Убрать пароль", callback_data="srv:clear_password")]] if password else []),
            [InlineKeyboardButton(text="◀ Назад", callback_data="nav:server")],
        ])
        await show_menu(callback, text, kb)
        return

    elif action == "set_password":
        _stop_refresh(callback.message.message_id)
        await callback.answer()
        await state.set_state(ServerState.waiting_password)
        await callback.message.answer(
            "Введи новый пароль для сервера:", reply_markup=CANCEL_REPLY_KB
        )
        return

    elif action == "clear_password":
        _stop_refresh(callback.message.message_id)
        await callback.answer()
        await db.set_setting("server_password", "")
        text = success_text("Пароль убран.")
        await _show_server_menu(callback)
        return

    # Actions that take time — stop refresh during execution
    _stop_refresh(callback.message.message_id)
    await callback.answer("Выполняю...")

    if action == "start":
        logger.info(f"Server start [{callback.from_user.id}]")
        result = await docker_manager.start()
        await callback.message.edit_text(result, reply_markup=_server_kb, parse_mode="HTML")
        # Start refresh to show status updates
        await asyncio.sleep(2)
        await _show_server_menu(callback)

    elif action == "stop":
        logger.info(f"Server stop [{callback.from_user.id}]")
        if await docker_manager.is_running():
            await rcon.execute("say Сервер будет остановлен через 10 секунд!")
            await callback.message.edit_text("⏳ Остановка через 10 секунд...", reply_markup=_server_kb, parse_mode="HTML")
            await asyncio.sleep(10)
        result = await docker_manager.stop()
        await callback.message.edit_text(result, reply_markup=_server_kb, parse_mode="HTML")
        await asyncio.sleep(2)
        await _show_server_menu(callback)

    elif action == "restart":
        logger.info(f"Server restart [{callback.from_user.id}]")
        if await docker_manager.is_running():
            await rcon.execute("say Сервер перезапускается через 10 секунд!")
            await callback.message.edit_text("⏳ Рестарт через 10 секунд...", reply_markup=_server_kb, parse_mode="HTML")
            await asyncio.sleep(10)
        result = await docker_manager.restart()
        await callback.message.edit_text(result, reply_markup=_server_kb, parse_mode="HTML")
        await asyncio.sleep(2)
        await _show_server_menu(callback)

    elif action == "logs":
        lines = int(parts[2]) if len(parts) > 2 else 50
        logs = await docker_manager.logs(lines=lines)
        logs = clean_log(logs)
        result = f"<pre>{truncate(logs)}</pre>"
        try:
            await callback.message.edit_text(result, reply_markup=_server_kb, parse_mode="HTML")
        except Exception:
            await callback.message.answer(result, reply_markup=_server_kb, parse_mode="HTML")

    else:
        await callback.message.edit_text("Неизвестная команда.", reply_markup=_server_kb, parse_mode="HTML")


@server_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(ServerState.waiting_password),
)
async def cancel_password(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@server_router.message(StateFilter(ServerState.waiting_password))
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    if not password:
        await message.answer("Введи пароль:")
        return

    await state.clear()
    await db.set_setting("server_password", password)
    logger.info(f"Server password changed by [{message.from_user.id}]")
    await message.answer(success_text(f"Пароль установлен: <code>{password}</code>"))
    text = await _build_status_text()
    await message.answer(text, reply_markup=_server_kb, parse_mode="HTML")
