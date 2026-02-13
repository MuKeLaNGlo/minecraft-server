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
from states.states import AdminState
from utils.formatting import section_header, success_text, error_text
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

admin_router = Router()

ADMIN_MENU_TEXT = section_header(
    "👤", "Доступ к боту",
    "Кто может пользоваться ботом.\n"
    "Админ — полный доступ. Пользователь — мониторинг, игроки, RCON.\n"
    "Также: чёрный список RCON-команд.",
)

_admin_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Роли", callback_data="adm:roles"),
            InlineKeyboardButton(text="📝 Команды", callback_data="adm:commands"),
        ],
        back_row("main"),
    ]
)

_roles_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Выдать", callback_data="adm:give"),
            InlineKeyboardButton(text="📝 Снять", callback_data="adm:remove"),
        ],
        [InlineKeyboardButton(text="◀ Назад", callback_data="adm:back")],
    ]
)

_give_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🪪 Админ", callback_data="adm:role:give_admin"),
            InlineKeyboardButton(text="🪪 Обычный", callback_data="adm:role:give_user"),
        ],
        [InlineKeyboardButton(text="◀ Назад", callback_data="adm:roles")],
    ]
)

_remove_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🪪 Админ", callback_data="adm:role:remove_admin"),
            InlineKeyboardButton(text="🪪 Обычный", callback_data="adm:role:remove_user"),
        ],
        [InlineKeyboardButton(text="◀ Назад", callback_data="adm:roles")],
    ]
)


@admin_router.callback_query(F.data == "nav:admin")
async def admin_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await show_menu(callback, ADMIN_MENU_TEXT, _admin_kb)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm:"))
async def admin_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]
    await callback.answer()

    if action == "roles":
        await show_menu(callback, "Управление ролями:", _roles_kb)

    elif action == "give":
        await show_menu(callback, "Выбери тип роли для выдачи:", _give_kb)

    elif action == "remove":
        await show_menu(callback, "Выбери тип роли для снятия:", _remove_kb)

    elif action == "role":
        role_action = parts[2]  # give_admin, give_user, remove_admin, remove_user
        await state.update_data(admin_role_action=role_action)
        await state.set_state(AdminState.add_admin)  # generic "waiting for ID" state
        prompts = {
            "give_admin": "Введи Telegram ID для выдачи прав администратора:",
            "give_user": "Введи Telegram ID для выдачи доступа:",
            "remove_admin": "Введи Telegram ID для снятия прав администратора:",
            "remove_user": "Введи Telegram ID для снятия доступа:",
        }
        await callback.message.answer(
            prompts.get(role_action, "Введи Telegram ID:"),
            reply_markup=CANCEL_REPLY_KB,
        )

    elif action == "commands":
        blocked = await db.commands_all()
        if blocked:
            cmd_list = "\n".join(f"  - <code>{c}</code>" for c in blocked)
            text = f"<b>Заблокированные команды:</b>\n{cmd_list}"
        else:
            text = "Список заблокированных команд пуст."

        commands_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⛔ Добавить", callback_data="adm:cmd_add"),
                    InlineKeyboardButton(text="🗑 Удалить", callback_data="adm:cmd_remove"),
                ],
                [InlineKeyboardButton(text="◀ Назад", callback_data="adm:back")],
            ]
        )
        await show_menu(callback, text, commands_kb)

    elif action == "cmd_add":
        await state.set_state(AdminState.command_add)
        await callback.message.answer(
            "Введи команду для блокировки:", reply_markup=CANCEL_REPLY_KB
        )

    elif action == "cmd_remove":
        await state.set_state(AdminState.command_remove)
        await callback.message.answer(
            "Введи команду для разблокировки:", reply_markup=CANCEL_REPLY_KB
        )

    elif action == "back":
        await show_menu(callback, ADMIN_MENU_TEXT, _admin_kb)


# --- FSM: cancel from any admin state ---
@admin_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(
        AdminState.add_admin,
        AdminState.command_add,
        AdminState.command_remove,
    ),
)
async def cancel_admin(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


# --- FSM: process role ID input ---
@admin_router.message(StateFilter(AdminState.add_admin))
async def process_role_id(message: Message, state: FSMContext):
    text_id = message.text.strip()
    if not text_id.isdigit():
        await message.answer("ID должен содержать только цифры. Попробуй ещё раз:")
        return

    data = await state.get_data()
    role_action = data.get("admin_role_action", "")

    if role_action == "give_admin":
        if await db.check_admin(text_id):
            result = f"Пользователь {text_id} уже является администратором."
        else:
            await db.add_admin(text_id)
            logger.info(f"Admin added: {text_id} by {message.from_user.id}")
            result = success_text(f"Администратор выдан пользователю {text_id}.")

    elif role_action == "give_user":
        if await db.user_exists(text_id):
            result = f"Пользователь {text_id} уже имеет доступ."
        else:
            await db.add_user(text_id)
            logger.info(f"User added: {text_id} by {message.from_user.id}")
            result = success_text(f"Доступ выдан пользователю {text_id}.")

    elif role_action == "remove_admin":
        if not await db.check_admin(text_id):
            result = f"Пользователь {text_id} не является администратором."
        else:
            await db.admin_remove(text_id)
            logger.info(f"Admin removed: {text_id} by {message.from_user.id}")
            result = success_text(f"Права администратора сняты с {text_id}.")

    elif role_action == "remove_user":
        if not await db.user_exists(text_id):
            result = f"Пользователь {text_id} не найден."
        else:
            await db.user_remove(text_id)
            logger.info(f"User removed: {text_id} by {message.from_user.id}")
            result = success_text(f"Доступ снят с пользователя {text_id}.")
    else:
        result = "Неизвестное действие."

    await state.clear()
    await message.answer(result)
    await message.answer(ADMIN_MENU_TEXT, reply_markup=_admin_kb, parse_mode="HTML")


# --- FSM: process command add ---
@admin_router.message(StateFilter(AdminState.command_add))
async def process_command_add(message: Message, state: FSMContext):
    command = message.text.strip().lower()

    if await db.command_exists(command):
        result = f"Команда <code>{command}</code> уже заблокирована."
    else:
        await db.add_black_list(command)
        logger.info(f"Command blocked: {command} by {message.from_user.id}")
        result = success_text(f"Команда <code>{command}</code> заблокирована.")

    await state.clear()
    await message.answer(result)
    await message.answer(ADMIN_MENU_TEXT, reply_markup=_admin_kb, parse_mode="HTML")


# --- FSM: process command remove ---
@admin_router.message(StateFilter(AdminState.command_remove))
async def process_command_remove(message: Message, state: FSMContext):
    command = message.text.strip().lower()

    if not await db.command_exists(command):
        result = f"Команда <code>{command}</code> не заблокирована."
    else:
        await db.remove_black_list(command)
        logger.info(f"Command unblocked: {command} by {message.from_user.id}")
        result = success_text(f"Команда <code>{command}</code> разблокирована.")

    await state.clear()
    await message.answer(result)
    await message.answer(ADMIN_MENU_TEXT, reply_markup=_admin_kb, parse_mode="HTML")
