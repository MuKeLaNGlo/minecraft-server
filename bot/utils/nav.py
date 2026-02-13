from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from db.database import db
from utils.logger import logger

# Minimal reply KB — fallback if inline message is lost
MENU_REPLY_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📋 Меню")]],
    resize_keyboard=True,
)

CANCEL_REPLY_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="◀ Отмена")]],
    resize_keyboard=True,
)


def back_row(target: str = "main") -> list:
    """Return a row with a single Back button."""
    return [InlineKeyboardButton(text="◀ Назад", callback_data=f"nav:{target}")]


def restart_row() -> list:
    """Return a row with a server restart button."""
    return [InlineKeyboardButton(text="🔄 Перезапустить сервер", callback_data="srv:restart")]


async def main_menu_kb(user_id: str | int) -> InlineKeyboardMarkup:
    """Build role-based inline main menu."""
    user_id = str(user_id)
    is_admin = await db.check_admin(user_id)
    has_access = await db.user_exists(user_id)

    buttons = []

    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="🖥 Сервер", callback_data="nav:server"),
            InlineKeyboardButton(text="👥 Игроки", callback_data="nav:players"),
        ])
        buttons.append([
            InlineKeyboardButton(text="📦 Моды", callback_data="nav:mods"),
            InlineKeyboardButton(text="💾 Бэкапы", callback_data="nav:backups"),
        ])
        buttons.append([
            InlineKeyboardButton(text="🌍 Миры", callback_data="nav:worlds"),
            InlineKeyboardButton(text="⚙ Настройки", callback_data="nav:config"),
        ])
        buttons.append([
            InlineKeyboardButton(text="📊 Мониторинг", callback_data="nav:monitoring"),
            InlineKeyboardButton(text="📈 Статистика", callback_data="nav:stats"),
        ])
        buttons.append([
            InlineKeyboardButton(text="⏰ Планировщик", callback_data="nav:scheduler"),
        ])
        buttons.append([
            InlineKeyboardButton(text="🎮 RCON", callback_data="nav:console"),
            InlineKeyboardButton(text="🔑 Доступ к боту", callback_data="nav:admin"),
        ])
        buttons.append([
            InlineKeyboardButton(text="🤖 Бот", callback_data="nav:bot_settings"),
        ])
    elif has_access:
        buttons.append([
            InlineKeyboardButton(text="📊 Мониторинг", callback_data="nav:monitoring"),
            InlineKeyboardButton(text="👥 Игроки", callback_data="nav:players"),
        ])
        buttons.append([
            InlineKeyboardButton(text="🎮 RCON", callback_data="nav:console"),
            InlineKeyboardButton(text="📈 Статистика", callback_data="nav:stats"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="📊 Мониторинг", callback_data="nav:monitoring"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_menu(
    event: CallbackQuery | Message,
    text: str,
    kb: InlineKeyboardMarkup,
    parse_mode: str = "HTML",
) -> Message:
    """Edit current message if callback, otherwise send new.

    Returns the sent/edited Message.
    """
    if isinstance(event, CallbackQuery):
        # Stop auto-refresh if active on this message (e.g. leaving server menu)
        _cancel_refresh(event.message.message_id)
        try:
            return await event.message.edit_text(text, reply_markup=kb, parse_mode=parse_mode)
        except Exception as e:
            logger.debug(f"show_menu edit failed, sending new: {e}")
            return await event.message.answer(text, reply_markup=kb, parse_mode=parse_mode)
    else:
        return await event.answer(text, reply_markup=kb, parse_mode=parse_mode)


def _cancel_refresh(msg_id: int) -> None:
    """Cancel server auto-refresh task for a message, if any."""
    from routers.server import active_refresh_tasks
    task = active_refresh_tasks.pop(msg_id, None)
    if task and not task.done():
        task.cancel()


async def return_to_menu(message: Message) -> None:
    """Send main menu with inline KB and restore reply KB after FSM cancel."""
    from utils.formatting import section_header

    text = section_header("🏠", "Главное меню", "Выбери раздел для управления сервером.")
    kb = await main_menu_kb(message.from_user.id)
    # Restore reply KB (replaces "◀ Отмена" with "📋 Меню")
    await message.answer("Готово.", reply_markup=MENU_REPLY_KB)
    # Show inline menu
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def check_admin(callback: CallbackQuery) -> bool:
    """Check if callback user is admin. Answers with denial if not."""
    if await db.check_admin(str(callback.from_user.id)):
        return True
    await callback.answer("⛔ Нет доступа", show_alert=True)
    return False


async def check_access(callback: CallbackQuery) -> bool:
    """Check if callback user has at least 'user' access."""
    uid = str(callback.from_user.id)
    if await db.check_admin(uid) or await db.user_exists(uid):
        return True
    await callback.answer("⛔ Нет доступа", show_alert=True)
    return False
