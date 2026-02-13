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
from minecraft.rcon import rcon
from states.states import ServerState
from utils.formatting import truncate, section_header, progress_bar, status_dot, clean_log, success_text
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB


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

server_router = Router()

SERVER_MENU_TEXT = section_header(
    "🖥", "Сервер",
    "Запуск, остановка и перезапуск сервера.\nПросмотр логов и текущего статуса.",
)

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
            InlineKeyboardButton(text="📊 Статус", callback_data="srv:status"),
            InlineKeyboardButton(text="🔒 Пароль", callback_data="srv:password"),
        ],
        back_row("main"),
    ]
)


@server_router.callback_query(F.data == "nav:server")
async def server_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await show_menu(callback, SERVER_MENU_TEXT, _server_kb)
    await callback.answer()


@server_router.callback_query(F.data.startswith("srv:"))
async def server_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "password":
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
        await callback.answer()
        await state.set_state(ServerState.waiting_password)
        await callback.message.answer(
            "Введи новый пароль для сервера:", reply_markup=CANCEL_REPLY_KB
        )
        return

    elif action == "clear_password":
        await callback.answer()
        await db.set_setting("server_password", "")
        text = success_text("Пароль убран.")
        await show_menu(callback, text, _server_kb)
        return

    await callback.answer("Выполняю...")

    if action == "start":
        logger.info(f"Server start [{callback.from_user.id}]")
        result = await docker_manager.start()

    elif action == "stop":
        logger.info(f"Server stop [{callback.from_user.id}]")
        if await docker_manager.is_running():
            await rcon.execute("say Сервер будет остановлен через 10 секунд!")
            await asyncio.sleep(10)
        result = await docker_manager.stop()

    elif action == "restart":
        logger.info(f"Server restart [{callback.from_user.id}]")
        if await docker_manager.is_running():
            await rcon.execute("say Сервер перезапускается через 10 секунд!")
            await asyncio.sleep(10)
        result = await docker_manager.restart()

    elif action == "logs":
        lines = int(parts[2]) if len(parts) > 2 else 50
        logs = await docker_manager.logs(lines=lines)
        logs = clean_log(logs)
        result = f"<pre>{truncate(logs)}</pre>"

    elif action == "status":
        status = await docker_manager.status()
        if status.get("status") == "not_found":
            result = "Контейнер не найден."
        elif status.get("status") == "error":
            result = f"Ошибка: {status.get('health')}"
        else:
            mem_mb = status.get("memory_mb", 0)
            limit_mb = status.get("memory_limit_mb", 0)
            mem_pct = (mem_mb / limit_mb * 100) if limit_mb > 0 else 0
            cpu = status.get("cpu_percent", 0)

            started_at = status.get("started_at", "")
            uptime = _format_uptime(started_at) if started_at else "—"

            result = (
                f"<b>📊 Статус сервера</b>\n\n"
                f"Состояние: {status['status']}\n"
                f"Здоровье: {status['health']}\n\n"
                f"CPU: {status_dot(cpu)} {progress_bar(cpu, 100)} {cpu:.1f}%\n"
                f"RAM: {status_dot(mem_pct)} {progress_bar(mem_mb, limit_mb)} "
                f"{mem_mb:.0f}/{limit_mb:.0f} МБ\n\n"
                f"⏱ Аптайм: <b>{uptime}</b>"
            )
    else:
        result = "Неизвестная команда."

    try:
        await callback.message.edit_text(result, reply_markup=_server_kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(result, reply_markup=_server_kb, parse_mode="HTML")


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
    await message.answer(SERVER_MENU_TEXT, reply_markup=_server_kb, parse_mode="HTML")
