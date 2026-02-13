"""RCON command presets organized by category.

Commands without 'params' execute immediately.
Commands with 'params' enter FSM to collect each parameter.
"""

RCON_CATEGORIES = {
    "time": {
        "label": "🕐 Время",
        "commands": [
            {"label": "🌅 Утро", "cmd": "time set day"},
            {"label": "🌙 Ночь", "cmd": "time set night"},
            {"label": "🌄 Рассвет", "cmd": "time set 0"},
            {"label": "🌇 Закат", "cmd": "time set 12000"},
        ],
    },
    "weather": {
        "label": "🌤 Погода",
        "commands": [
            {"label": "☀ Ясно", "cmd": "weather clear"},
            {"label": "🌧 Дождь", "cmd": "weather rain"},
            {"label": "⛈ Гроза", "cmd": "weather thunder"},
        ],
    },
    "gamemode": {
        "label": "🎮 Режим игры",
        "commands": [
            {"label": "⛏ Выживание", "cmd": "gamemode survival {player}", "params": [("player", "Имя игрока")]},
            {"label": "🎨 Творческий", "cmd": "gamemode creative {player}", "params": [("player", "Имя игрока")]},
            {"label": "👁 Наблюдатель", "cmd": "gamemode spectator {player}", "params": [("player", "Имя игрока")]},
            {"label": "🗺 Приключение", "cmd": "gamemode adventure {player}", "params": [("player", "Имя игрока")]},
        ],
    },
    "tp": {
        "label": "🧭 Телепортация",
        "commands": [
            {"label": "📍 К игроку", "cmd": "tp {player1} {player2}", "params": [("player1", "Кого телепортировать"), ("player2", "К кому")]},
            {"label": "🏠 На спавн", "cmd": "tp {player} 0 ~ 0", "params": [("player", "Имя игрока")]},
            {"label": "📌 На координаты", "cmd": "tp {player} {x} {y} {z}", "params": [("player", "Имя игрока"), ("x", "X координата"), ("y", "Y координата"), ("z", "Z координата")]},
        ],
    },
    "give": {
        "label": "🎁 Выдать",
        "commands": [
            {"label": "💎 Алмазы x64", "cmd": "give {player} diamond 64", "params": [("player", "Имя игрока")]},
            {"label": "🍖 Еда x64", "cmd": "give {player} cooked_beef 64", "params": [("player", "Имя игрока")]},
            {"label": "🏹 Оружие", "cmd": "give {player} diamond_sword 1", "params": [("player", "Имя игрока")]},
            {"label": "✏ Свой предмет", "cmd": "give {player} {item} {count}", "params": [("player", "Имя игрока"), ("item", "ID предмета (напр. iron_ingot)"), ("count", "Количество")]},
        ],
    },
    "server": {
        "label": "🖥 Сервер",
        "commands": [
            {"label": "📋 Онлайн", "cmd": "list"},
            {"label": "💬 Объявление", "cmd": "say {message}", "params": [("message", "Текст объявления")]},
            {"label": "🔒 Сохранить", "cmd": "save-all"},
            {"label": "🔨 Сложность", "cmd": "difficulty {level}", "params": [("level", "peaceful/easy/normal/hard")]},
        ],
    },
}


def get_category_list():
    """Return list of (key, label) for category buttons."""
    return [(key, cat["label"]) for key, cat in RCON_CATEGORIES.items()]


def get_command(cat_key: str, cmd_idx: int):
    """Get a command dict by category key and index."""
    cat = RCON_CATEGORIES.get(cat_key)
    if not cat:
        return None
    commands = cat.get("commands", [])
    if 0 <= cmd_idx < len(commands):
        return commands[cmd_idx]
    return None
