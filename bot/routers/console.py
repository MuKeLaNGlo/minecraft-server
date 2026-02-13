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
from utils.keyboards import player_selector_kb
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


async def _ask_param(reply_func, state, param_tuple, cmd_text: str, first: bool = False):
    """Ask for a parameter — show player buttons if type is 'player', else text input.

    reply_func: an awaitable like message.answer or callback.message.answer
    """
    param_key, param_prompt, param_type = param_tuple

    if param_type == "player":
        kb = await player_selector_kb(
            manual_callback="rcon:manual_param",
            back_callback="rcon:back",
            player_callback_prefix="rconpl",
        )
        if kb:
            prefix = f"Команда: <code>{cmd_text}</code>\n\n" if first else ""
            await reply_func(
                f"{prefix}<b>{param_prompt}</b> — выбери игрока:", reply_markup=kb,
            )
            return

    # Text param or no online players — FSM text input
    await state.set_state(RconState.waiting_preset_params)
    prefix = f"Команда: <code>{cmd_text}</code>\n\n" if first else ""
    await reply_func(
        f"{prefix}Введи <b>{param_prompt}</b>:", reply_markup=CANCEL_REPLY_KB,
    )


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
            await _ask_param(callback.message.answer, state, params[0], cmd["cmd"], first=True)
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

    elif action == "manual_param":
        # Switch from player buttons to text input for current param
        await callback.answer()
        await state.set_state(RconState.waiting_preset_params)
        data = await state.get_data()
        cmd = get_command(data.get("preset_cat", ""), data.get("preset_idx", 0))
        param_index = data.get("preset_param_index", 0)
        if cmd:
            params = cmd.get("params", [])
            if param_index < len(params):
                _, prompt, _ = params[param_index]
                await callback.message.answer(
                    f"Введи <b>{prompt}</b>:", reply_markup=CANCEL_REPLY_KB,
                )
                return
        await callback.message.answer("Введи значение:", reply_markup=CANCEL_REPLY_KB)

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


async def _collect_param_and_continue(state: FSMContext, value: str, reply_func, uid: str):
    """Collect a param value, ask next or execute. Returns True if handled."""
    data = await state.get_data()
    cat_key = data["preset_cat"]
    cmd_idx = data["preset_idx"]
    params_collected = data.get("preset_params", {})
    param_index = data.get("preset_param_index", 0)

    cmd = get_command(cat_key, cmd_idx)
    if not cmd:
        await state.clear()
        await reply_func(error_text("Команда не найдена."))
        return

    params = cmd.get("params", [])
    param_key = params[param_index][0]
    params_collected[param_key] = value

    # Check if more params needed
    next_index = param_index + 1
    if next_index < len(params):
        await state.update_data(preset_params=params_collected, preset_param_index=next_index)
        await _ask_param(reply_func, state, params[next_index], cmd["cmd"])
        return

    # All params collected — build and execute command
    await state.clear()
    command_text = cmd["cmd"]
    for k, v in params_collected.items():
        command_text = command_text.replace(f"{{{k}}}", v)

    is_admin = await db.check_admin(uid)
    first_word = command_text.split(" ", 1)[0].lower()
    if not is_admin and await db.command_exists(first_word):
        await reply_func("⛔ Команда заблокирована.")
        return

    result = await rcon.execute(command_text)
    response = truncate(result) if result.strip() else "(пустой ответ)"

    logger.info(f"RCON preset [{uid}]: {command_text} -> {result[:200]}")
    await log_to_group(bot, f"RCON [{uid}]: {command_text}")

    text = (
        success_text(f"Выполнено: <code>{command_text}</code>") + "\n\n"
        f"Ответ: <code>{response}</code>"
    )
    await reply_func(text)
    await reply_func(CONSOLE_TEXT, reply_markup=_console_main_kb(), parse_mode="HTML")


@console_router.callback_query(F.data.startswith("rconpl:"))
async def rcon_player_selected(callback: CallbackQuery, state: FSMContext):
    """Handle player selection from inline buttons in RCON presets."""
    player_name = callback.data.split(":", 1)[1]
    await callback.answer()
    uid = str(callback.from_user.id)
    await _collect_param_and_continue(state, player_name, callback.message.answer, uid)


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
    uid = str(message.from_user.id)
    await _collect_param_and_continue(state, value, message.answer, uid)


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
