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
from minecraft.player_manager import player_manager
from states.states import PlayerState
from datetime import datetime, timezone
from utils.formatting import format_duration, section_header, success_text
from utils.logger import logger
from utils.nav import check_admin, check_access, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

players_router = Router()

def _format_last_seen(last_seen_str: str) -> str:
    """Format last_seen timestamp into a short relative string."""
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


async def _get_online_names() -> list[str]:
    """Get list of online player names. Returns [] if server is down."""
    try:
        data = await player_manager.get_online_players()
        return data.get("players", [])
    except Exception:
        return []


async def _players_menu_text() -> str:
    """Build players menu text with online players and recent activity."""
    online = await _get_online_names()

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
        [InlineKeyboardButton(text="📊 Статистика", callback_data="pl:stats")],
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

    action = callback.data.split(":")[1]
    await callback.answer()

    if action == "banlist":
        result = await player_manager.banlist()
        text = result if result.strip() else "Банлист пуст."
        await show_menu(callback, text, _players_kb)

    elif action == "wl_list":
        result = await player_manager.whitelist_list()
        text = result if result.strip() else "Whitelist пуст."
        await show_menu(callback, text, _players_kb)

    elif action == "stats":
        stats = await db.get_all_player_stats()
        if not stats:
            text = "Статистика пока пуста."
        else:
            lines = ["<b>📊 Статистика игроков</b>\n"]
            for s in stats[:15]:
                name, sessions, total_secs, last_seen, is_online = s
                status = "🟢" if is_online else "⚪"
                lines.append(
                    f"{status} <b>{name}</b>: {format_duration(total_secs)} "
                    f"({sessions} сессий)"
                )
            text = "\n".join(lines)
        await show_menu(callback, text, _players_kb)

    elif action in ("kick", "ban", "pardon", "wl_add", "wl_remove", "op", "deop"):
        await state.update_data(player_action=action)
        online = await _get_online_names()
        if online:
            buttons = []
            row = []
            for name in online:
                row.append(InlineKeyboardButton(
                    text=name, callback_data=f"plsel:{name[:40]}",
                ))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton(
                text="✏ Ввести вручную", callback_data="pl:manual_name",
            )])
            buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="nav:players")])
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
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

    if action == "kick":
        result = await player_manager.kick(player_name)
    elif action == "ban":
        result = await player_manager.ban(player_name)
    elif action == "pardon":
        result = await player_manager.pardon(player_name)
    elif action == "wl_add":
        result = await player_manager.whitelist_add(player_name)
    elif action == "wl_remove":
        result = await player_manager.whitelist_remove(player_name)
    elif action == "op":
        result = await player_manager.op(player_name)
    elif action == "deop":
        result = await player_manager.deop(player_name)
    elif gamemode:
        result = await player_manager.gamemode(player_name, gamemode)
    else:
        result = "Неизвестное действие."

    logger.info(f"Player action [{callback.from_user.id}]: {action or 'gamemode'} {player_name}")
    await state.clear()

    response = result if result.strip() else success_text("Команда выполнена.")
    text = await _players_menu_text()
    full = f"{response}\n\n{text}"
    await show_menu(callback, full, _players_kb)


@players_router.callback_query(F.data.startswith("gm:"), StateFilter(PlayerState.waiting_gamemode))
async def gamemode_select(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(gamemode=mode, player_action=None)
    online = await _get_online_names()
    if online:
        buttons = []
        row = []
        for name in online:
            row.append(InlineKeyboardButton(
                text=name, callback_data=f"plsel:{name[:40]}",
            ))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton(
            text="✏ Ввести вручную", callback_data="pl:manual_name",
        )])
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="nav:players")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
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

    if action == "kick":
        result = await player_manager.kick(player_name)
    elif action == "ban":
        result = await player_manager.ban(player_name)
    elif action == "pardon":
        result = await player_manager.pardon(player_name)
    elif action == "wl_add":
        result = await player_manager.whitelist_add(player_name)
    elif action == "wl_remove":
        result = await player_manager.whitelist_remove(player_name)
    elif action == "op":
        result = await player_manager.op(player_name)
    elif action == "deop":
        result = await player_manager.deop(player_name)
    elif gamemode:
        result = await player_manager.gamemode(player_name, gamemode)
    else:
        result = "Неизвестное действие."

    logger.info(f"Player action [{message.from_user.id}]: {action or 'gamemode'} {player_name}")

    response = result if result.strip() else success_text("Команда выполнена.")
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
