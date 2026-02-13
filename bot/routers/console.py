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
from minecraft.rcon import rcon
from minecraft.rcon_presets import RCON_CATEGORIES, get_command
from states.states import RconState
from utils.formatting import truncate, section_header, success_text, error_text
from core.loader import bot
from utils.logger import logger, log_to_group
from utils.nav import check_access, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

console_router = Router()

CONSOLE_TEXT = section_header(
    "🎮", "RCON Консоль",
    "Выполнение команд на сервере.\nБыстрые пресеты или ручной ввод.",
)


def _console_main_kb() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for key, cat in RCON_CATEGORIES.items():
        row.append(InlineKeyboardButton(text=cat["label"], callback_data=f"rcon:cat:{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⌨ Ввести команду", callback_data="rcon:manual")])
    buttons.append(back_row("main"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@console_router.callback_query(F.data == "nav:console")
async def enter_rcon(callback: CallbackQuery, state: FSMContext):
    if not await check_access(callback):
        return
    await callback.answer()
    await show_menu(callback, CONSOLE_TEXT, _console_main_kb())


@console_router.callback_query(F.data.startswith("rcon:"))
async def rcon_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_access(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "cat":
        cat_key = parts[2]
        cat = RCON_CATEGORIES.get(cat_key)
        if not cat:
            await callback.answer("Категория не найдена")
            return
        await callback.answer()

        buttons = []
        row = []
        for idx, cmd in enumerate(cat["commands"]):
            row.append(InlineKeyboardButton(
                text=cmd["label"],
                callback_data=f"rcon:exec:{cat_key}:{idx}",
            ))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="rcon:back")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = f"<b>{cat['label']}</b> — быстрые команды"
        await show_menu(callback, text, kb)

    elif action == "exec":
        cat_key = parts[2]
        cmd_idx = int(parts[3])
        cmd = get_command(cat_key, cmd_idx)
        if not cmd:
            await callback.answer("Команда не найдена")
            return

        # If command has params, enter FSM
        params = cmd.get("params", [])
        if params:
            await callback.answer()
            await state.update_data(
                preset_cat=cat_key,
                preset_idx=cmd_idx,
                preset_params={},
                preset_param_index=0,
            )
            await state.set_state(RconState.waiting_preset_params)
            param_key, param_prompt = params[0]
            await callback.message.answer(
                f"Команда: <code>{cmd['cmd']}</code>\n\n"
                f"Введи <b>{param_prompt}</b>:",
                reply_markup=CANCEL_REPLY_KB,
            )
            return

        # Execute immediately
        await callback.answer("Выполняю...")
        command_text = cmd["cmd"]
        uid = str(callback.from_user.id)

        result = await rcon.execute(command_text)
        response = truncate(result) if result.strip() else "(пустой ответ)"

        logger.info(f"RCON preset [{uid}]: {command_text} -> {result[:200]}")
        await log_to_group(bot, f"RCON [{uid}]: {command_text}")

        text = (
            success_text(f"Выполнено: <code>{command_text}</code>") + "\n\n"
            f"Ответ: <code>{response}</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ К категории", callback_data=f"rcon:cat:{cat_key}")],
            [InlineKeyboardButton(text="◀ К пресетам", callback_data="rcon:back")],
        ])
        await show_menu(callback, text, kb)

    elif action == "manual":
        await callback.answer()
        await state.set_state(RconState.waiting_command)
        await callback.message.answer(
            "Введи RCON команду.\nДля выхода нажми <b>◀ Отмена</b>.",
            reply_markup=CANCEL_REPLY_KB,
        )

    elif action == "back":
        await callback.answer()
        await show_menu(callback, CONSOLE_TEXT, _console_main_kb())


@console_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(RconState.waiting_command, RconState.waiting_preset_params),
)
async def cancel_rcon(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@console_router.message(StateFilter(RconState.waiting_preset_params))
async def process_preset_param(message: Message, state: FSMContext):
    value = message.text.strip()
    if not value:
        await message.answer("Введи значение:")
        return

    data = await state.get_data()
    cat_key = data["preset_cat"]
    cmd_idx = data["preset_idx"]
    params_collected = data.get("preset_params", {})
    param_index = data.get("preset_param_index", 0)

    cmd = get_command(cat_key, cmd_idx)
    if not cmd:
        await state.clear()
        await message.answer(error_text("Команда не найдена."))
        return

    params = cmd.get("params", [])
    param_key, _ = params[param_index]
    params_collected[param_key] = value

    # Check if more params needed
    next_index = param_index + 1
    if next_index < len(params):
        await state.update_data(preset_params=params_collected, preset_param_index=next_index)
        next_key, next_prompt = params[next_index]
        await message.answer(f"Введи <b>{next_prompt}</b>:")
        return

    # All params collected — build and execute command
    await state.clear()
    command_text = cmd["cmd"]
    for k, v in params_collected.items():
        command_text = command_text.replace(f"{{{k}}}", v)

    uid = str(message.from_user.id)
    is_admin = await db.check_admin(uid)

    first_word = command_text.split(" ", 1)[0].lower()
    if not is_admin and await db.command_exists(first_word):
        await message.answer("⛔ Команда заблокирована.")
        return

    result = await rcon.execute(command_text)
    response = truncate(result) if result.strip() else "(пустой ответ)"

    logger.info(f"RCON preset [{uid}]: {command_text} -> {result[:200]}")
    await log_to_group(bot, f"RCON [{uid}]: {command_text}")

    text = (
        success_text(f"Выполнено: <code>{command_text}</code>") + "\n\n"
        f"Ответ: <code>{response}</code>"
    )
    await message.answer(text)
    await message.answer(CONSOLE_TEXT, reply_markup=_console_main_kb(), parse_mode="HTML")


@console_router.message(StateFilter(RconState.waiting_command))
async def execute_rcon(message: Message, state: FSMContext):
    chat_id = str(message.from_user.id)
    command_text = message.text.strip()
    is_admin = await db.check_admin(chat_id)

    first_word = command_text.split(" ", 1)[0].lower()
    if not is_admin and await db.command_exists(first_word):
        await message.answer("⛔ Команда заблокирована.")
        return

    result = await rcon.execute(command_text)
    response = truncate(result) if result.strip() else "(пустой ответ)"

    logger.info(f"RCON [{chat_id}]: {command_text} -> {result[:200]}")
    await log_to_group(bot, f"RCON [{chat_id}]: {command_text}")

    await message.answer(f"<code>{response}</code>")
