"""Reusable keyboard builders for common UI patterns."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from minecraft.player_manager import player_manager


async def get_online_names() -> list[str]:
    """Get list of online player names. Returns [] if server is down."""
    try:
        data = await player_manager.get_online_players()
        return data.get("players", [])
    except Exception:
        return []


async def player_selector_kb(
    manual_callback: str,
    back_callback: str,
    player_callback_prefix: str = "plsel",
    cols: int = 2,
) -> InlineKeyboardMarkup | None:
    """Build keyboard with online players + manual input option.

    Returns None if no players are online (caller should fall back to FSM).
    """
    online = await get_online_names()
    if not online:
        return None

    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for name in online:
        row.append(InlineKeyboardButton(
            text=name, callback_data=f"{player_callback_prefix}:{name[:40]}",
        ))
        if len(row) == cols:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="✏ Ввести вручную", callback_data=manual_callback)])
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
