from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from core.config import config
from db.database import db
from states.states import AdminState
from utils.formatting import section_header, success_text, error_text, LINE
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

admin_router = Router()

ADMIN_MENU_TEXT = section_header(
    "👤", "Доступ к боту",
    "Управление пользователями и правами доступа.",
)


def _admin_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛡 Админы", callback_data="adm:list_admins")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:list_users")],
            [InlineKeyboardButton(text="⛔ Чёрный список команд", callback_data="adm:commands")],
            back_row("main"),
        ]
    )


async def _resolve_name(bot, telegram_id: str) -> str:
    """Try to get user's display name via Telegram API."""
    try:
        chat = await bot.get_chat(int(telegram_id))
        name = chat.full_name or chat.username or telegram_id
        return name
    except Exception:
        return telegram_id


@admin_router.callback_query(F.data == "nav:admin")
async def admin_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await show_menu(callback, ADMIN_MENU_TEXT, _admin_kb())
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm:"))
async def admin_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]
    await callback.answer()

    # --- Admin list ---
    if action == "list_admins":
        admins = await db.get_all_admins()
        buttons = []
        for tid in admins:
            name = await _resolve_name(callback.bot, tid)
            is_super = int(tid) == config.super_admin_id
            label = f"🛡 {name} ({tid})"
            if is_super:
                label += " · владелец"
            buttons.append([InlineKeyboardButton(
                text=label,
                callback_data=f"adm:admin_detail:{tid}",
            )])
        buttons.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm:add:admin")])
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="adm:back")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, f"🛡 <b>Администраторы</b> ({len(admins)}):", kb)

    elif action == "admin_detail":
        tid = parts[2]
        name = await _resolve_name(callback.bot, tid)
        is_super = int(tid) == config.super_admin_id
        text = (
            f"{LINE}\n"
            f"🛡 <b>{name}</b>\n"
            f"{LINE}\n\n"
            f"ID: <code>{tid}</code>\n"
            f"Роль: {'Владелец (суперадмин)' if is_super else 'Администратор'}"
        )
        buttons = []
        if not is_super:
            buttons.append([
                InlineKeyboardButton(text="⬇ Понизить до пользователя", callback_data=f"adm:demote:{tid}"),
                InlineKeyboardButton(text="🗑 Убрать доступ", callback_data=f"adm:remove_confirm:{tid}:admin"),
            ])
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="adm:list_admins")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, text, kb)

    elif action == "demote":
        tid = parts[2]
        if int(tid) == config.super_admin_id:
            await show_menu(callback, error_text("Нельзя понизить владельца."), _admin_kb())
            return
        name = await _resolve_name(callback.bot, tid)
        await db.admin_remove(tid)
        await db.add_user(tid)
        logger.info(f"Admin {tid} demoted to user by {callback.from_user.id}")
        await show_menu(callback, success_text(f"{name} понижен до пользователя."), _admin_kb())

    # --- User list ---
    elif action == "list_users":
        users = await db.get_all_users()
        buttons = []
        for tid in users:
            name = await _resolve_name(callback.bot, tid)
            buttons.append([InlineKeyboardButton(
                text=f"👤 {name} ({tid})",
                callback_data=f"adm:user_detail:{tid}",
            )])
        buttons.append([InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="adm:add:user")])
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="adm:back")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, f"👥 <b>Пользователи</b> ({len(users)}):", kb)

    elif action == "user_detail":
        tid = parts[2]
        name = await _resolve_name(callback.bot, tid)
        text = (
            f"{LINE}\n"
            f"👤 <b>{name}</b>\n"
            f"{LINE}\n\n"
            f"ID: <code>{tid}</code>\n"
            f"Роль: Пользователь"
        )
        buttons = [
            [
                InlineKeyboardButton(text="⬆ Повысить до админа", callback_data=f"adm:promote:{tid}"),
                InlineKeyboardButton(text="🗑 Убрать доступ", callback_data=f"adm:remove_confirm:{tid}:user"),
            ],
            [InlineKeyboardButton(text="◀ Назад", callback_data="adm:list_users")],
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, text, kb)

    elif action == "promote":
        tid = parts[2]
        name = await _resolve_name(callback.bot, tid)
        await db.user_remove(tid)
        await db.add_admin(tid)
        logger.info(f"User {tid} promoted to admin by {callback.from_user.id}")
        await show_menu(callback, success_text(f"{name} повышен до администратора."), _admin_kb())

    # --- Remove confirmation ---
    elif action == "remove_confirm":
        tid = parts[2]
        role = parts[3]  # "admin" or "user"
        if role == "admin" and int(tid) == config.super_admin_id:
            await show_menu(callback, error_text("Нельзя удалить владельца."), _admin_kb())
            return
        name = await _resolve_name(callback.bot, tid)
        role_label = "администратора" if role == "admin" else "пользователя"
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, убрать", callback_data=f"adm:remove_do:{tid}:{role}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm:list_{role}s"),
            ],
        ])
        await show_menu(callback, f"Убрать доступ {role_label} <b>{name}</b> ({tid})?", confirm_kb)

    elif action == "remove_do":
        tid = parts[2]
        role = parts[3]
        name = await _resolve_name(callback.bot, tid)
        if role == "admin":
            await db.admin_remove(tid)
            logger.info(f"Admin removed: {tid} by {callback.from_user.id}")
        else:
            await db.user_remove(tid)
            logger.info(f"User removed: {tid} by {callback.from_user.id}")
        await show_menu(callback, success_text(f"Доступ {name} ({tid}) снят."), _admin_kb())

    # --- Add admin/user ---
    elif action == "add":
        role = parts[2]  # "admin" or "user"
        await state.update_data(admin_add_role=role)
        await state.set_state(AdminState.add_admin)
        role_label = "администратора" if role == "admin" else "пользователя"
        await callback.message.answer(
            f"Введи Telegram ID нового {role_label}:",
            reply_markup=CANCEL_REPLY_KB,
        )

    # --- Commands blacklist ---
    elif action == "commands":
        blocked = await db.commands_all()
        if blocked:
            buttons = []
            for cmd in blocked:
                buttons.append([InlineKeyboardButton(
                    text=f"🗑 {cmd}", callback_data=f"adm:cmd_del:{cmd}",
                )])
            text = f"⛔ <b>Заблокированные команды</b> ({len(blocked)}):"
        else:
            buttons = []
            text = "Список заблокированных команд пуст."
        buttons.append([InlineKeyboardButton(text="➕ Добавить команду", callback_data="adm:cmd_add")])
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="adm:back")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, text, kb)

    elif action == "cmd_add":
        await state.set_state(AdminState.command_add)
        await callback.message.answer(
            "Введи команду для блокировки:", reply_markup=CANCEL_REPLY_KB
        )

    elif action == "cmd_del":
        cmd = parts[2]
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, разблокировать", callback_data=f"adm:cmd_del_confirm:{cmd}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="adm:commands"),
            ],
        ])
        await show_menu(callback, f"Разблокировать команду <code>{cmd}</code>?", confirm_kb)

    elif action == "cmd_del_confirm":
        cmd = parts[2]
        await db.remove_black_list(cmd)
        logger.info(f"Command unblocked: {cmd} by {callback.from_user.id}")
        await show_menu(callback, success_text(f"Команда <code>{cmd}</code> разблокирована."), _admin_kb())

    elif action == "back":
        await show_menu(callback, ADMIN_MENU_TEXT, _admin_kb())


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


# --- FSM: process add admin/user by ID ---
@admin_router.message(StateFilter(AdminState.add_admin))
async def process_add_id(message: Message, state: FSMContext):
    text_id = message.text.strip()
    if not text_id.isdigit():
        await message.answer("ID должен содержать только цифры. Попробуй ещё раз:")
        return

    data = await state.get_data()
    role = data.get("admin_add_role", "user")

    name = await _resolve_name(message.bot, text_id)

    if role == "admin":
        if await db.check_admin(text_id):
            result = f"{name} ({text_id}) уже является администратором."
        else:
            await db.add_admin(text_id)
            logger.info(f"Admin added: {text_id} by {message.from_user.id}")
            result = success_text(f"🛡 {name} ({text_id}) — администратор.")
    else:
        if await db.user_exists(text_id):
            result = f"{name} ({text_id}) уже имеет доступ."
        else:
            await db.add_user(text_id)
            logger.info(f"User added: {text_id} by {message.from_user.id}")
            result = success_text(f"👤 {name} ({text_id}) — пользователь.")

    await state.clear()
    await message.answer(result, parse_mode="HTML")
    await message.answer(ADMIN_MENU_TEXT, reply_markup=_admin_kb(), parse_mode="HTML")


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
    await message.answer(result, parse_mode="HTML")
    await message.answer(ADMIN_MENU_TEXT, reply_markup=_admin_kb(), parse_mode="HTML")
