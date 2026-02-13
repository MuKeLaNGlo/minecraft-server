"""RCON command presets organized by category.

Commands without 'params' execute immediately.
Commands with 'params' enter FSM to collect each parameter.

Param tuples: (key, prompt, type)
  type "player" = show online player buttons
  type "text"   = text input
"""

# Shorthand for player param
_P = ("player", "Имя игрока", "player")

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
            {"label": "⛏ Выживание", "cmd": "gamemode survival {player}", "params": [_P]},
            {"label": "🎨 Творческий", "cmd": "gamemode creative {player}", "params": [_P]},
            {"label": "👁 Наблюдатель", "cmd": "gamemode spectator {player}", "params": [_P]},
            {"label": "🗺 Приключение", "cmd": "gamemode adventure {player}", "params": [_P]},
        ],
    },
    "tp": {
        "label": "🧭 Телепортация",
        "commands": [
            {"label": "📍 К игроку", "cmd": "tp {player1} {player2}", "params": [("player1", "Кого телепортировать", "player"), ("player2", "К кому", "player")]},
            {"label": "🏠 На спавн", "cmd": "tp {player} 0 ~ 0", "params": [_P]},
            {"label": "📌 На координаты", "cmd": "tp {player} {x} {y} {z}", "params": [_P, ("x", "X координата", "text"), ("y", "Y координата", "text"), ("z", "Z координата", "text")]},
        ],
    },
    # ── Give: items by sub-categories ────────────────────────────
    "give_res": {
        "label": "💎 Ресурсы",
        "commands": [
            {"label": "💎 Алмазы x64", "cmd": "give {player} diamond 64", "params": [_P]},
            {"label": "🟡 Золото x64", "cmd": "give {player} gold_ingot 64", "params": [_P]},
            {"label": "⬜ Железо x64", "cmd": "give {player} iron_ingot 64", "params": [_P]},
            {"label": "🟢 Изумруды x64", "cmd": "give {player} emerald 64", "params": [_P]},
            {"label": "🔵 Лазурит x64", "cmd": "give {player} lapis_lazuli 64", "params": [_P]},
            {"label": "🔴 Редстоун x64", "cmd": "give {player} redstone 64", "params": [_P]},
            {"label": "💠 Незерит", "cmd": "give {player} netherite_ingot 16", "params": [_P]},
            {"label": "🪨 Обсидиан x64", "cmd": "give {player} obsidian 64", "params": [_P]},
        ],
    },
    "give_food": {
        "label": "🍖 Еда",
        "commands": [
            {"label": "🥩 Стейк x64", "cmd": "give {player} cooked_beef 64", "params": [_P]},
            {"label": "🍗 Курица x64", "cmd": "give {player} cooked_chicken 64", "params": [_P]},
            {"label": "🍞 Хлеб x64", "cmd": "give {player} bread 64", "params": [_P]},
            {"label": "🥕 Морковь x64", "cmd": "give {player} golden_carrot 64", "params": [_P]},
            {"label": "🍎 Зол. яблоко x8", "cmd": "give {player} golden_apple 8", "params": [_P]},
            {"label": "🍏 Зач. яблоко", "cmd": "give {player} enchanted_golden_apple 1", "params": [_P]},
        ],
    },
    "give_armor": {
        "label": "🛡 Броня",
        "commands": [
            {"label": "⛑ Алм. шлем", "cmd": "give {player} diamond_helmet 1", "params": [_P]},
            {"label": "🦺 Алм. нагрудник", "cmd": "give {player} diamond_chestplate 1", "params": [_P]},
            {"label": "👖 Алм. поножи", "cmd": "give {player} diamond_leggings 1", "params": [_P]},
            {"label": "👢 Алм. ботинки", "cmd": "give {player} diamond_boots 1", "params": [_P]},
            {"label": "⛑ Незер. шлем", "cmd": "give {player} netherite_helmet 1", "params": [_P]},
            {"label": "🦺 Незер. нагрудник", "cmd": "give {player} netherite_chestplate 1", "params": [_P]},
            {"label": "👖 Незер. поножи", "cmd": "give {player} netherite_leggings 1", "params": [_P]},
            {"label": "👢 Незер. ботинки", "cmd": "give {player} netherite_boots 1", "params": [_P]},
        ],
    },
    "give_weapon": {
        "label": "⚔ Оружие",
        "commands": [
            {"label": "⚔ Алм. меч", "cmd": "give {player} diamond_sword 1", "params": [_P]},
            {"label": "🏹 Лук", "cmd": "give {player} bow 1", "params": [_P]},
            {"label": "🏹 Арбалет", "cmd": "give {player} crossbow 1", "params": [_P]},
            {"label": "🔱 Трезубец", "cmd": "give {player} trident 1", "params": [_P]},
            {"label": "⚔ Незер. меч", "cmd": "give {player} netherite_sword 1", "params": [_P]},
            {"label": "🪓 Незер. топор", "cmd": "give {player} netherite_axe 1", "params": [_P]},
            {"label": "🏹 Стрелы x64", "cmd": "give {player} arrow 64", "params": [_P]},
        ],
    },
    "give_tools": {
        "label": "⛏ Инструменты",
        "commands": [
            {"label": "⛏ Алм. кирка", "cmd": "give {player} diamond_pickaxe 1", "params": [_P]},
            {"label": "🪓 Алм. топор", "cmd": "give {player} diamond_axe 1", "params": [_P]},
            {"label": "🔨 Алм. лопата", "cmd": "give {player} diamond_shovel 1", "params": [_P]},
            {"label": "🎣 Удочка", "cmd": "give {player} fishing_rod 1", "params": [_P]},
            {"label": "⛏ Незер. кирка", "cmd": "give {player} netherite_pickaxe 1", "params": [_P]},
            {"label": "🪓 Незер. топор", "cmd": "give {player} netherite_axe 1", "params": [_P]},
            {"label": "🔨 Незер. лопата", "cmd": "give {player} netherite_shovel 1", "params": [_P]},
            {"label": "🌾 Незер. мотыга", "cmd": "give {player} netherite_hoe 1", "params": [_P]},
        ],
    },
    "give_transport": {
        "label": "🚀 Транспорт",
        "commands": [
            {"label": "🪂 Элитры", "cmd": "give {player} elytra 1", "params": [_P]},
            {"label": "🚀 Фейерверки x64", "cmd": "give {player} firework_rocket 64", "params": [_P]},
            {"label": "🚣 Лодка", "cmd": "give {player} oak_boat 1", "params": [_P]},
            {"label": "🛤 Рельсы x64", "cmd": "give {player} rail 64", "params": [_P]},
            {"label": "⚡ Энерг. рельсы x32", "cmd": "give {player} powered_rail 32", "params": [_P]},
            {"label": "🛒 Вагонетка", "cmd": "give {player} minecart 1", "params": [_P]},
            {"label": "🐴 Седло", "cmd": "give {player} saddle 1", "params": [_P]},
        ],
    },
    "give_potions": {
        "label": "🧪 Зелья",
        "commands": [
            {"label": "❤ Лечение x8", "cmd": 'give {player} potion{Potion:"minecraft:strong_healing"} 8', "params": [_P]},
            {"label": "💪 Сила x8", "cmd": 'give {player} potion{Potion:"minecraft:strong_strength"} 8', "params": [_P]},
            {"label": "🏃 Скорость x8", "cmd": 'give {player} potion{Potion:"minecraft:strong_swiftness"} 8', "params": [_P]},
            {"label": "🛡 Огнестойкость x8", "cmd": 'give {player} potion{Potion:"minecraft:fire_resistance"} 8', "params": [_P]},
            {"label": "👁 Ночное зрение x8", "cmd": 'give {player} potion{Potion:"minecraft:night_vision"} 8', "params": [_P]},
            {"label": "🫧 Подв. дыхание x8", "cmd": 'give {player} potion{Potion:"minecraft:water_breathing"} 8', "params": [_P]},
            {"label": "👻 Невидимость x8", "cmd": 'give {player} potion{Potion:"minecraft:invisibility"} 8', "params": [_P]},
        ],
    },
    "give_special": {
        "label": "✨ Особое",
        "commands": [
            {"label": "🌟 Бут. опыта x64", "cmd": "give {player} experience_bottle 64", "params": [_P]},
            {"label": "🔮 Жемчуг Края x16", "cmd": "give {player} ender_pearl 16", "params": [_P]},
            {"label": "📦 Шалкер. ящик", "cmd": "give {player} shulker_box 1", "params": [_P]},
            {"label": "🧭 Компас", "cmd": "give {player} recovery_compass 1", "params": [_P]},
            {"label": "🪣 Ведро воды", "cmd": "give {player} water_bucket 1", "params": [_P]},
            {"label": "🗿 Тотем", "cmd": "give {player} totem_of_undying 1", "params": [_P]},
            {"label": "📖 Зач. книга", "cmd": "give {player} enchanted_book 1", "params": [_P]},
            {"label": "✏ Свой предмет", "cmd": "give {player} {item} {count}", "params": [_P, ("item", "ID предмета (напр. iron_ingot)", "text"), ("count", "Количество", "text")]},
        ],
    },
    # ── Effects ──────────────────────────────────────────────────
    "effects": {
        "label": "⚡ Эффекты",
        "commands": [
            {"label": "❤ Регенерация", "cmd": "effect give {player} regeneration 120 1", "params": [_P]},
            {"label": "💪 Сила", "cmd": "effect give {player} strength 300 1", "params": [_P]},
            {"label": "🏃 Скорость", "cmd": "effect give {player} speed 300 1", "params": [_P]},
            {"label": "🛡 Сопротивление", "cmd": "effect give {player} resistance 300 1", "params": [_P]},
            {"label": "⬆ Прыгучесть", "cmd": "effect give {player} jump_boost 300 2", "params": [_P]},
            {"label": "👻 Невидимость", "cmd": "effect give {player} invisibility 300", "params": [_P]},
            {"label": "🌟 Свечение", "cmd": "effect give {player} glowing 120", "params": [_P]},
            {"label": "🚫 Снять все", "cmd": "effect clear {player}", "params": [_P]},
        ],
    },
    # ── Server ───────────────────────────────────────────────────
    "server": {
        "label": "🖥 Сервер",
        "commands": [
            {"label": "📋 Онлайн", "cmd": "list"},
            {"label": "💬 Объявление", "cmd": "say {message}", "params": [("message", "Текст объявления", "text")]},
            {"label": "🔒 Сохранить", "cmd": "save-all"},
            {"label": "🔨 Сложность", "cmd": "difficulty {level}", "params": [("level", "peaceful/easy/normal/hard", "text")]},
            {"label": "🌱 Сид мира", "cmd": "seed"},
            {"label": "👢 Кикнуть", "cmd": "kick {player} {reason}", "params": [_P, ("reason", "Причина (можно пусто)", "text")]},
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
