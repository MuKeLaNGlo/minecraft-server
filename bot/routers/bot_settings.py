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
from states.states import BotSettingsState
from utils.formatting import section_header, success_text
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

bot_settings_router = Router()


async def _build_settings_text() -> str:
    notif = await db.get_setting("notifications_enabled") == "1"
    bridge = await db.get_setting("chat_bridge_enabled") == "1"
    chat_id = await db.get_setting("notifications_chat_id")

    return section_header(
        "🤖", "Настройки бота",
        "Управление уведомлениями о входе/выходе игроков\n"
        "и трансляцией сообщений между Telegram и Minecraft.",
    ) + (
        f"\n\nУведомления: {'✅ вкл' if notif else '❌ выкл'}\n"
        f"Чат-мост: {'✅ вкл' if bridge else '❌ выкл'}\n"
        f"ID чата: <code>{chat_id or 'не задан'}</code>"
    )


async def _settings_kb() -> InlineKeyboardMarkup:
    notif = await db.get_setting("notifications_enabled") == "1"
    bridge = await db.get_setting("chat_bridge_enabled") == "1"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔔 Уведомления: {'ВКЛ' if notif else 'ВЫКЛ'}",
                callback_data="bset:toggle_notif",
            )],
            [InlineKeyboardButton(
                text=f"💬 Чат-мост: {'ВКЛ' if bridge else 'ВЫКЛ'}",
                callback_data="bset:toggle_bridge",
            )],
            [InlineKeyboardButton(
                text="📍 Указать чат",
                callback_data="bset:set_chat",
            )],
            back_row("main"),
        ]
    )


@bot_settings_router.callback_query(F.data == "nav:bot_settings")
async def bot_settings_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.answer()
    text = await _build_settings_text()
    kb = await _settings_kb()
    await show_menu(callback, text, kb)


@bot_settings_router.callback_query(F.data.startswith("bset:"))
async def bot_settings_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    action = callback.data.split(":")[1]

    if action == "toggle_notif":
        current = await db.get_setting("notifications_enabled")
        new_val = "0" if current == "1" else "1"
        await db.set_setting("notifications_enabled", new_val)
        logger.info(f"Notifications {'enabled' if new_val == '1' else 'disabled'} [{callback.from_user.id}]")
        await callback.answer("Уведомления " + ("включены" if new_val == "1" else "выключены"))

        text = await _build_settings_text()
        kb = await _settings_kb()
        await show_menu(callback, text, kb)

    elif action == "toggle_bridge":
        current = await db.get_setting("chat_bridge_enabled")
        new_val = "0" if current == "1" else "1"
        await db.set_setting("chat_bridge_enabled", new_val)
        logger.info(f"Chat bridge {'enabled' if new_val == '1' else 'disabled'} [{callback.from_user.id}]")
        await callback.answer("Чат-мост " + ("включён" if new_val == "1" else "выключен"))

        text = await _build_settings_text()
        kb = await _settings_kb()
        await show_menu(callback, text, kb)

    elif action == "set_chat":
        await callback.answer()
        await state.set_state(BotSettingsState.waiting_chat_id)
        current = await db.get_setting("notifications_chat_id")
        await callback.message.answer(
            f"Текущий ID чата: <code>{current or 'не задан'}</code>\n\n"
            "Введи ID чата для уведомлений, или перешли любое сообщение из нужной группы.\n\n"
            "💡 Чтобы узнать ID, добавь бота в группу и используй /id.",
            reply_markup=CANCEL_REPLY_KB,
        )


@bot_settings_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(BotSettingsState.waiting_chat_id),
)
async def cancel_set_chat(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@bot_settings_router.message(StateFilter(BotSettingsState.waiting_chat_id))
async def process_chat_id(message: Message, state: FSMContext):
    # Accept forwarded message — extract chat ID
    if message.forward_from_chat:
        chat_id = str(message.forward_from_chat.id)
    else:
        chat_id = message.text.strip()

    # Basic validation
    if not chat_id.lstrip("-").isdigit():
        await message.answer("ID должен быть числом (может начинаться с -). Попробуй ещё раз:")
        return

    await db.set_setting("notifications_chat_id", chat_id)
    logger.info(f"Notifications chat_id set to {chat_id} [{message.from_user.id}]")
    await state.clear()

    await message.answer(success_text(f"ID чата установлен: <code>{chat_id}</code>"))

    text = await _build_settings_text()
    kb = await _settings_kb()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
