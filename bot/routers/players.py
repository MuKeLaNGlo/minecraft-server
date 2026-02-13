from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import html

from db.database import db
from minecraft.player_manager import player_manager
from states.states import PlayerState
from utils.formatting import section_header, success_text
from utils.keyboards import player_selector_kb, get_online_names
from utils.logger import logger
from utils.nav import check_access, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

players_router = Router()

def _format_last_seen(last_seen_str: str) -> str:
    """Format last_seen timestamp into a short relative string."""
    from datetime import datetime, timezone
    try:
        last_seen = datetime.fromisoformat(last_seen_str).replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last_seen
        secs = int(delta.total_seconds())
        if secs < 60:
            return "только что"
        if secs < 3600:
            return f"{secs // 60}м назад"
        if secs < 86400:
            return f"{secs // 3600}ч назад"
        return f"{secs // 86400}д назад"
    except (ValueError, TypeError):
        return "—"


async def _players_menu_text() -> str:
    """Build players menu text with online players and recent activity."""
    online = await get_online_names()

    if online:
        online_str = ", ".join(f"<b>{p}</b>" for p in online)
        desc = f"🟢 Онлайн ({len(online)}): {online_str}"
    else:
        desc = "⚪ Никого нет на сервере"

    header = section_header(
        "👥", "Игроки",
        f"{desc}\n\nУправление: бан, вайтлист, права опера.\nОпер — права админа внутри игры.",
    )
    recent = await db.get_recent_players(24)
    if not recent:
        return header

    # Show only offline recent players (online already shown above)
    offline = [(name, last_seen) for name, last_seen, is_online in recent[:10] if not is_online]
    if not offline:
        return header

    lines = ["\n<b>Были недавно:</b>"]
    for name, last_seen in offline:
        lines.append(f"  ⚪ {name} — {_format_last_seen(last_seen)}")
    return header + "\n".join(lines)

_players_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="👢 Кик", callback_data="pl:kick"),
            InlineKeyboardButton(text="🔨 Бан", callback_data="pl:ban"),
        ],
        [
            InlineKeyboardButton(text="🕊 Разбан", callback_data="pl:pardon"),
            InlineKeyboardButton(text="📋 Банлист", callback_data="pl:banlist"),
        ],
        [
            InlineKeyboardButton(text="📃 Белый список", callback_data="pl:wl_list"),
            InlineKeyboardButton(text="➕ Добавить", callback_data="pl:wl_add"),
        ],
        [
            InlineKeyboardButton(text="➖ Убрать из списка", callback_data="pl:wl_remove"),
        ],
        [
            InlineKeyboardButton(text="⭐ Дать опера", callback_data="pl:op"),
            InlineKeyboardButton(text="⛔ Снять опера", callback_data="pl:deop"),
        ],
        [
            InlineKeyboardButton(text="🎮 Режим игры", callback_data="pl:gamemode"),
            InlineKeyboardButton(text="📢 Объявление", callback_data="pl:say"),
        ],
        [InlineKeyboardButton(text="📈 Статистика", callback_data="nav:stats")],
        back_row("main"),
    ]
)



@players_router.callback_query(F.data == "nav:players")
async def players_menu(callback: CallbackQuery):
    if not await check_access(callback):
        return
    text = await _players_menu_text()
    await show_menu(callback, text, _players_kb)
    await callback.answer()


@players_router.callback_query(F.data.startswith("pl:"))
async def players_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_access(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]
    await callback.answer()

    if action == "banlist":
        result = await player_manager.banlist()
        text = html.escape(result) if result.strip() else "Банлист пуст."
        await show_menu(callback, text, _players_kb)

    elif action == "wl_list":
        result = await player_manager.whitelist_list()
        text = html.escape(result) if result.strip() else "Whitelist пуст."
        await show_menu(callback, text, _players_kb)

    elif action in ("kick", "ban", "pardon", "wl_add", "wl_remove", "op", "deop"):
        await state.update_data(player_action=action)
        kb = await player_selector_kb(
            manual_callback="pl:manual_name",
            back_callback="nav:players",
        )
        if kb:
            action_labels = {
                "kick": "👢 Кик", "ban": "🔨 Бан", "pardon": "🕊 Разбан",
                "wl_add": "➕ Whitelist", "wl_remove": "➖ Whitelist",
                "op": "⭐ Дать опера", "deop": "⛔ Снять опера",
            }
            await show_menu(callback, f"{action_labels.get(action, action)} — выбери игрока:", kb)
        else:
            await state.set_state(PlayerState.waiting_player_name)
            await callback.message.answer(
                "Введи ник игрока:", reply_markup=CANCEL_REPLY_KB
            )

    elif action == "manual_name":
        await state.set_state(PlayerState.waiting_player_name)
        await callback.message.answer(
            "Введи ник игрока:", reply_markup=CANCEL_REPLY_KB
        )

    elif action == "gamemode":
        gm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⛏ Выживание", callback_data="gm:survival"),
                    InlineKeyboardButton(text="🎨 Творческий", callback_data="gm:creative"),
                ],
                [
                    InlineKeyboardButton(text="🗺 Приключение", callback_data="gm:adventure"),
                    InlineKeyboardButton(text="👁 Наблюдатель", callback_data="gm:spectator"),
                ],
            ]
        )
        await state.set_state(PlayerState.waiting_gamemode)
        await callback.message.answer("Выбери режим:", reply_markup=gm_kb)

    elif action == "say":
        await state.set_state(PlayerState.waiting_say_text)
        await callback.message.answer(
            "Введи сообщение для всех игроков:", reply_markup=CANCEL_REPLY_KB
        )


_ACTION_MAP = {
    "kick": player_manager.kick,
    "ban": player_manager.ban,
    "pardon": player_manager.pardon,
    "wl_add": player_manager.whitelist_add,
    "wl_remove": player_manager.whitelist_remove,
    "op": player_manager.op,
    "deop": player_manager.deop,
}


async def _dispatch_player_action(player_name: str, action: str | None, gamemode: str | None) -> str:
    """Execute a player action and return the RCON result string."""
    if action and action in _ACTION_MAP:
        return await _ACTION_MAP[action](player_name)
    if gamemode:
        return await player_manager.gamemode(player_name, gamemode)
    return "Неизвестное действие."


@players_router.callback_query(F.data.startswith("plsel:"))
async def player_selected(callback: CallbackQuery, state: FSMContext):
    """Handle player selection from inline buttons."""
    player_name = callback.data.split(":", 1)[1]
    data = await state.get_data()
    action = data.get("player_action")
    gamemode = data.get("gamemode")

    if not action and not gamemode:
        await callback.answer("Действие не выбрано")
        return

    await callback.answer("Выполняю...")
    result = await _dispatch_player_action(player_name, action, gamemode)

    logger.info(f"Player action [{callback.from_user.id}]: {action or 'gamemode'} {player_name}")
    await state.clear()

    response = html.escape(result) if result.strip() else success_text("Команда выполнена.")
    text = await _players_menu_text()
    full = f"{response}\n\n{text}"
    await show_menu(callback, full, _players_kb)


@players_router.callback_query(F.data.startswith("gm:"), StateFilter(PlayerState.waiting_gamemode))
async def gamemode_select(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(gamemode=mode, player_action=None)
    kb = await player_selector_kb(
        manual_callback="pl:manual_name",
        back_callback="nav:players",
    )
    if kb:
        mode_labels = {
            "survival": "⛏ Выживание", "creative": "🎨 Творческий",
            "adventure": "🗺 Приключение", "spectator": "👁 Наблюдатель",
        }
        await show_menu(callback, f"🎮 {mode_labels.get(mode, mode)} — выбери игрока:", kb)
    else:
        await state.set_state(PlayerState.waiting_player_name)
        await callback.message.answer("Введи ник игрока:", reply_markup=CANCEL_REPLY_KB)


@players_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(
        PlayerState.waiting_player_name,
        PlayerState.waiting_say_text,
        PlayerState.waiting_gamemode,
    ),
)
async def cancel_player(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@players_router.message(StateFilter(PlayerState.waiting_player_name))
async def process_player_name(message: Message, state: FSMContext):
    player_name = message.text.strip()
    data = await state.get_data()
    action = data.get("player_action")
    gamemode = data.get("gamemode")

    result = await _dispatch_player_action(player_name, action, gamemode)
    logger.info(f"Player action [{message.from_user.id}]: {action or 'gamemode'} {player_name}")

    response = html.escape(result) if result.strip() else success_text("Команда выполнена.")
    await state.clear()
    await message.answer(response)
    menu_text = await _players_menu_text()
    await message.answer(menu_text, reply_markup=_players_kb, parse_mode="HTML")


@players_router.message(StateFilter(PlayerState.waiting_say_text))
async def process_say_text(message: Message, state: FSMContext):
    text = message.text.strip()
    await player_manager.say(text)
    logger.info(f"Say [{message.from_user.id}]: {text}")

    await state.clear()
    await message.answer(success_text("Сообщение отправлено."))
    menu_text = await _players_menu_text()
    await message.answer(menu_text, reply_markup=_players_kb, parse_mode="HTML")
