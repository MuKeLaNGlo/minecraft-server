from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from core.config import config, PLUGIN_LOADERS

# ──────────────────────────────────────────────────────────────────
# YAML config file paths (relative to mc_data_path)
# ──────────────────────────────────────────────────────────────────
_DATA = Path(config.mc_data_path)

YAML_FILES = {
    "paper": _DATA / "config" / "paper-world-defaults.yml",
    "paper-global": _DATA / "config" / "paper-global.yml",
    "pufferfish": _DATA / "pufferfish.yml",
    "purpur": _DATA / "purpur.yml",
    "spigot": _DATA / "spigot.yml",
    "bukkit": _DATA / "bukkit.yml",
}

# ──────────────────────────────────────────────────────────────────
# Property metadata: type determines UI in config_editor
# Types: bool, enum, range, text
# "file" key means YAML config; absent = server.properties
# "path" is dot-separated YAML path
# ──────────────────────────────────────────────────────────────────
EDITABLE_PROPERTIES = {
    # ── server.properties ──
    "difficulty": {
        "desc": "Сложность мира",
        "type": "enum",
        "values": ["peaceful", "easy", "normal", "hard"],
        "labels": ["☮ Мирная", "😊 Лёгкая", "⚔ Нормальная", "💀 Сложная"],
    },
    "gamemode": {
        "desc": "Режим игры по умолчанию",
        "type": "enum",
        "values": ["survival", "creative", "adventure", "spectator"],
        "labels": ["⛏ Выживание", "🎨 Творческий", "🗺 Приключение", "👁 Наблюдатель"],
    },
    "pvp": {
        "desc": "Урон между игроками",
        "type": "bool",
    },
    "hardcore": {
        "desc": "Хардкор (одна жизнь)",
        "type": "bool",
    },
    "allow-nether": {
        "desc": "Нижний мир",
        "type": "bool",
    },
    "spawn-monsters": {
        "desc": "Спавн мобов",
        "type": "bool",
    },
    "spawn-animals": {
        "desc": "Спавн животных",
        "type": "bool",
    },
    "online-mode": {
        "desc": "Онлайн-режим (проверка лицензии)",
        "type": "bool",
    },
    "white-list": {
        "desc": "Вайтлист",
        "type": "bool",
    },
    "enable-command-block": {
        "desc": "Командные блоки",
        "type": "bool",
    },
    "view-distance": {
        "desc": "Дальность прорисовки (чанки)",
        "type": "range",
        "min": 2,
        "max": 32,
        "presets": [("6", "6"), ("8", "8"), ("10", "⚙ 10"), ("12", "12"), ("16", "🚀 16")],
    },
    "simulation-distance": {
        "desc": "Дальность симуляции (чанки)",
        "type": "range",
        "min": 2,
        "max": 16,
        "presets": [("4", "🐢 4"), ("6", "⚙ 6"), ("8", "8"), ("10", "🚀 10")],
    },
    "max-players": {
        "desc": "Макс. игроков",
        "type": "range",
        "min": 1,
        "max": 100,
        "presets": [("5", "5"), ("10", "10"), ("20", "20"), ("50", "50")],
    },
    "spawn-protection": {
        "desc": "Защита спавна (радиус в блоках)",
        "type": "range",
        "min": 0,
        "max": 256,
        "presets": [("0", "Выкл"), ("8", "8"), ("16", "16"), ("32", "32")],
    },
    "motd": {
        "desc": "Описание сервера (MOTD)",
        "type": "text",
    },
    "level-name": {
        "desc": "Название мира",
        "type": "text",
    },
    "level-seed": {
        "desc": "Сид мира",
        "type": "text",
    },

    # ── paper-world-defaults.yml (optimization) ──
    "p:opt-expl": {
        "desc": "Оптимизация взрывов",
        "type": "bool",
        "file": "paper",
        "path": "environment.optimize-explosions",
    },
    "p:redstone": {
        "desc": "Реализация редстоуна",
        "type": "enum",
        "values": ["VANILLA", "EIGENCRAFT", "ALTERNATE_CURRENT"],
        "labels": ["🔴 Vanilla", "⚡ Eigencraft", "⚡ Alt Current"],
        "file": "paper",
        "path": "misc.redstone-implementation",
    },
    "p:chunk-unload": {
        "desc": "Задержка выгрузки чанков",
        "type": "enum",
        "values": ["5s", "10s", "15s", "30s"],
        "labels": ["5s", "10s (дефолт)", "15s", "30s"],
        "file": "paper",
        "path": "chunks.delay-chunk-unloads-by",
    },
    "p:autosave-chunks": {
        "desc": "Макс. чанков для автосохранения за тик",
        "type": "range",
        "min": 4,
        "max": 48,
        "presets": [("8", "8"), ("12", "12"), ("24", "⚙ 24")],
        "file": "paper",
        "path": "chunks.max-auto-save-chunks-per-tick",
    },
    "p:spawn-loaded": {
        "desc": "Загруженные чанки у спавна",
        "type": "range",
        "min": -1,
        "max": 20,
        "presets": [("-1", "Выкл"), ("3", "3"), ("5", "5"), ("10", "⚙ 10")],
        "file": "paper",
        "path": "spawn.keep-spawn-loaded-range",
    },
    "p:pathfinding": {
        "desc": "Пересчёт путей мобов при изменении блоков",
        "type": "bool",
        "file": "paper",
        "path": "misc.update-pathfinding-on-block-update",
    },
    "p:alt-despawn": {
        "desc": "Ускоренный деспавн мусора",
        "type": "bool",
        "file": "paper",
        "path": "entities.spawning.alt-item-despawn-rate.enabled",
    },
    "p:per-player-mobs": {
        "desc": "Спавн мобов на игрока (не глобально)",
        "type": "bool",
        "file": "paper",
        "path": "entities.spawning.per-player-mob-spawns",
    },
    "p:limit-arrow": {
        "desc": "Лимит стрел на чанк",
        "type": "range",
        "min": -1,
        "max": 100,
        "presets": [("-1", "Нет"), ("8", "8"), ("16", "⚙ 16"), ("32", "32")],
        "file": "paper",
        "path": "chunks.entity-per-chunk-save-limit.arrow",
    },
    "p:limit-epearl": {
        "desc": "Лимит эндерперлов на чанк",
        "type": "range",
        "min": -1,
        "max": 100,
        "presets": [("-1", "Нет"), ("8", "8"), ("16", "⚙ 16")],
        "file": "paper",
        "path": "chunks.entity-per-chunk-save-limit.ender_pearl",
    },
    "p:limit-xp": {
        "desc": "Лимит орбов опыта на чанк",
        "type": "range",
        "min": -1,
        "max": 100,
        "presets": [("-1", "Нет"), ("16", "16"), ("32", "⚙ 32")],
        "file": "paper",
        "path": "chunks.entity-per-chunk-save-limit.experience_orb",
    },
    "p:limit-snowball": {
        "desc": "Лимит снежков на чанк",
        "type": "range",
        "min": -1,
        "max": 100,
        "presets": [("-1", "Нет"), ("8", "8"), ("16", "⚙ 16")],
        "file": "paper",
        "path": "chunks.entity-per-chunk-save-limit.snowball",
    },

    # ── paper-global.yml ──
    "pg:chunk-send": {
        "desc": "Макс. скорость отправки чанков",
        "type": "range",
        "min": -1,
        "max": 200,
        "presets": [("-1", "Нет"), ("50", "50"), ("75", "⚙ 75"), ("100", "100")],
        "file": "paper-global",
        "path": "chunk-loading-basic.player-max-chunk-send-rate",
    },
    "pg:chunk-gen": {
        "desc": "Макс. скорость генерации чанков",
        "type": "range",
        "min": -1,
        "max": 100,
        "presets": [("-1", "Нет"), ("15", "15"), ("25", "⚙ 25"), ("40", "40")],
        "file": "paper-global",
        "path": "chunk-loading-basic.player-max-chunk-generate-rate",
    },

    # ── pufferfish.yml ──
    "pf:dab": {
        "desc": "DAB — мозг мобов по дистанции",
        "type": "bool",
        "file": "pufferfish",
        "path": "dab.enabled",
    },
    "pf:dab-freq": {
        "desc": "DAB макс. частота тиков",
        "type": "range",
        "min": 10,
        "max": 40,
        "presets": [("10", "10"), ("20", "⚙ 20"), ("30", "30")],
        "file": "pufferfish",
        "path": "dab.max-tick-freq",
    },
    "pf:goal-throttle": {
        "desc": "Троттлинг AI неактивных мобов",
        "type": "bool",
        "file": "pufferfish",
        "path": "inactive-goal-selector-throttle",
    },
    "pf:async-spawn": {
        "desc": "Асинхронный спавн мобов",
        "type": "bool",
        "file": "pufferfish",
        "path": "enable-async-mob-spawning",
    },

    # ── bukkit.yml ──
    "bk:mob-tick": {
        "desc": "Тиков между спавном монстров",
        "type": "range",
        "min": 1,
        "max": 20,
        "presets": [("1", "⚙ 1"), ("2", "2"), ("4", "4"), ("10", "10")],
        "file": "bukkit",
        "path": "ticks-per.monster-spawns",
    },
    "bk:mob-limit": {
        "desc": "Лимит монстров",
        "type": "range",
        "min": 10,
        "max": 100,
        "presets": [("30", "30"), ("50", "50"), ("70", "⚙ 70")],
        "file": "bukkit",
        "path": "spawn-limits.monsters",
    },
    "bk:animal-limit": {
        "desc": "Лимит животных",
        "type": "range",
        "min": 1,
        "max": 30,
        "presets": [("3", "3"), ("5", "5"), ("10", "⚙ 10")],
        "file": "bukkit",
        "path": "spawn-limits.animals",
    },

    # ── spigot.yml ──
    "sp:mob-range": {
        "desc": "Дальность спавна мобов (чанки)",
        "type": "range",
        "min": 2,
        "max": 10,
        "presets": [("3", "3"), ("6", "⚙ 6"), ("8", "⚙ 8")],
        "file": "spigot",
        "path": "world-settings.default.mob-spawn-range",
    },
    "sp:act-animals": {
        "desc": "Активация животных (блоки)",
        "type": "range",
        "min": 8,
        "max": 48,
        "presets": [("16", "16"), ("24", "24"), ("32", "⚙ 32")],
        "file": "spigot",
        "path": "world-settings.default.entity-activation-range.animals",
    },
    "sp:act-monsters": {
        "desc": "Активация монстров (блоки)",
        "type": "range",
        "min": 8,
        "max": 48,
        "presets": [("16", "16"), ("24", "24"), ("32", "⚙ 32")],
        "file": "spigot",
        "path": "world-settings.default.entity-activation-range.monsters",
    },
    "sp:merge-item": {
        "desc": "Радиус объединения предметов",
        "type": "enum",
        "values": ["2.5", "3.5", "4.0"],
        "labels": ["2.5 (дефолт)", "3.5", "4.0"],
        "file": "spigot",
        "path": "world-settings.default.merge-radius.item",
    },
    "sp:merge-exp": {
        "desc": "Радиус объединения опыта",
        "type": "enum",
        "values": ["3.0", "4.0", "6.0"],
        "labels": ["3.0 (дефолт)", "4.0", "6.0"],
        "file": "spigot",
        "path": "world-settings.default.merge-radius.exp",
    },
}

# ──────────────────────────────────────────────────────────────────
# Templates for quick apply
# ──────────────────────────────────────────────────────────────────
TEMPLATES = {
    "pvp": {
        "label": "⚔ PvP Арена",
        "desc": "Выживание + сложная сложность + урон между игроками",
        "pvp": "true",
        "difficulty": "hard",
        "gamemode": "survival",
        "hardcore": "false",
        "spawn-monsters": "true",
    },
    "survival": {
        "label": "⛏ Выживание",
        "desc": "Классика: нормальная сложность, без PvP, мобы",
        "pvp": "false",
        "difficulty": "normal",
        "gamemode": "survival",
        "hardcore": "false",
        "spawn-monsters": "true",
    },
    "creative": {
        "label": "🎨 Творческий",
        "desc": "Мирный режим, творческий режим игры, без PvP",
        "pvp": "false",
        "difficulty": "peaceful",
        "gamemode": "creative",
        "hardcore": "false",
    },
    "hardcore": {
        "label": "💀 Хардкор",
        "desc": "Одна жизнь, макс. сложность, PvP и мобы",
        "pvp": "true",
        "difficulty": "hard",
        "gamemode": "survival",
        "hardcore": "true",
        "spawn-monsters": "true",
    },
    "optimize": {
        "label": "🚀 Оптимизация",
        "desc": "Оптимальные настройки для производительности",
        "properties": {
            # server.properties
            "view-distance": "10",
            "simulation-distance": "6",
            # paper-world-defaults
            "p:opt-expl": "true",
            "p:redstone": "ALTERNATE_CURRENT",
            "p:autosave-chunks": "8",
            "p:spawn-loaded": "3",
            "p:pathfinding": "false",
            "p:alt-despawn": "true",
            "p:limit-arrow": "16",
            "p:limit-epearl": "8",
            "p:limit-xp": "16",
            "p:limit-snowball": "8",
            # paper-global
            "pg:chunk-gen": "25",
            # pufferfish
            "pf:dab": "true",
            "pf:goal-throttle": "true",
            # spigot
            "sp:merge-item": "3.5",
            "sp:merge-exp": "4.0",
        },
    },
}

# ──────────────────────────────────────────────────────────────────
# Category definitions for config_editor UI
# ──────────────────────────────────────────────────────────────────
PROPERTY_CATEGORIES = {
    "performance": {
        "label": "⚡ Производительность",
        "desc": "Дальность прорисовки, симуляции и лимиты",
        "properties": ["view-distance", "simulation-distance", "max-players", "spawn-protection"],
    },
    "gameplay": {
        "label": "🎮 Геймплей",
        "desc": "Режим игры, сложность и PvP",
        "properties": ["difficulty", "gamemode", "pvp", "hardcore", "allow-nether"],
    },
    "world": {
        "label": "🌍 Мир",
        "desc": "Название, сид и спавн мобов",
        "properties": ["level-name", "level-seed", "spawn-monsters", "spawn-animals"],
    },
    "network": {
        "label": "🌐 Сеть",
        "desc": "Онлайн-режим, вайтлист и MOTD",
        "properties": ["online-mode", "white-list", "enable-command-block", "motd"],
    },
}

# Paper/Purpur-only optimization categories
if config.mc_loader in PLUGIN_LOADERS:
    PROPERTY_CATEGORIES["paper_opt"] = {
        "label": "📄 Paper",
        "desc": "Чанки, редстоун, сущности",
        "properties": [
            "p:opt-expl",
            "p:redstone",
            "p:chunk-unload",
            "p:autosave-chunks",
            "p:spawn-loaded",
            "p:pathfinding",
            "p:alt-despawn",
            "p:per-player-mobs",
        ],
    }
    PROPERTY_CATEGORIES["paper_entities"] = {
        "label": "🐾 Лимиты сущностей",
        "desc": "Лимиты сохранения и чанков",
        "properties": [
            "p:limit-arrow",
            "p:limit-epearl",
            "p:limit-xp",
            "p:limit-snowball",
            "pg:chunk-send",
            "pg:chunk-gen",
        ],
    }
    PROPERTY_CATEGORIES["pufferfish_opt"] = {
        "label": "🐡 Pufferfish",
        "desc": "DAB, AI мобов, асинхронный спавн",
        "properties": [
            "pf:dab",
            "pf:dab-freq",
            "pf:goal-throttle",
            "pf:async-spawn",
        ],
    }
    PROPERTY_CATEGORIES["spigot_opt"] = {
        "label": "🔧 Spigot/Bukkit",
        "desc": "Спавн мобов, активация, объединение",
        "properties": [
            "sp:mob-range",
            "sp:act-animals",
            "sp:act-monsters",
            "sp:merge-item",
            "sp:merge-exp",
            "bk:mob-tick",
            "bk:mob-limit",
            "bk:animal-limit",
        ],
    }


# ──────────────────────────────────────────────────────────────────
# YAML reading/writing helpers
# ──────────────────────────────────────────────────────────────────

def _yaml_read(file_key: str) -> dict:
    """Read a YAML config file and return its data as dict."""
    path = YAML_FILES.get(file_key)
    if not path or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _yaml_write(file_key: str, data: dict) -> bool:
    """Write dict back to YAML config file, preserving structure."""
    path = YAML_FILES.get(file_key)
    if not path or not path.exists():
        return False
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return True


def _yaml_get(data: dict, dotted_path: str) -> Any:
    """Get a value from nested dict using dot-separated path."""
    keys = dotted_path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _yaml_set(data: dict, dotted_path: str, value: Any) -> bool:
    """Set a value in nested dict using dot-separated path."""
    keys = dotted_path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return True


def _coerce_yaml_value(raw: str, current: Any = None) -> Any:
    """Convert string value to proper YAML type based on content or existing type."""
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    # Try int
    try:
        return int(raw)
    except ValueError:
        pass
    # Try float
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ──────────────────────────────────────────────────────────────────
# ServerConfig class
# ──────────────────────────────────────────────────────────────────

class ServerConfig:
    def __init__(self):
        self.path = Path(config.mc_data_path) / "server.properties"

    # ── server.properties ──

    def read_properties(self) -> Dict[str, str]:
        """Parse server.properties into a dict."""
        props = {}
        if not self.path.exists():
            return props
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    props[key.strip()] = value.strip()
        return props

    def get_property(self, key: str) -> Optional[str]:
        """Get a property value. Works for both server.properties and YAML configs."""
        meta = EDITABLE_PROPERTIES.get(key, {})
        if isinstance(meta, dict) and "file" in meta:
            return self._get_yaml_property(key)
        props = self.read_properties()
        return props.get(key)

    def write_property(self, key: str, value: str) -> bool:
        """Write a property. Works for both server.properties and YAML configs."""
        meta = EDITABLE_PROPERTIES.get(key, {})
        if isinstance(meta, dict) and "file" in meta:
            return self._write_yaml_property(key, value)
        return self._write_properties_file(key, value)

    def _write_properties_file(self, key: str, value: str) -> bool:
        """Update a single property in server.properties."""
        if not self.path.exists():
            return False

        lines = self.path.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                lines[i] = f"{key}={value}"
                found = True
                break

        if not found:
            lines.append(f"{key}={value}")

        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    # ── YAML configs ──

    def _get_yaml_property(self, key: str) -> Optional[str]:
        """Read a YAML property by its key from EDITABLE_PROPERTIES."""
        meta = EDITABLE_PROPERTIES.get(key, {})
        if not isinstance(meta, dict) or "file" not in meta:
            return None
        file_key = meta["file"]
        dotted_path = meta["path"]
        data = _yaml_read(file_key)
        if not data:
            return None
        val = _yaml_get(data, dotted_path)
        if val is None:
            return None
        return str(val)

    def _write_yaml_property(self, key: str, value: str) -> bool:
        """Write a YAML property by its key from EDITABLE_PROPERTIES."""
        meta = EDITABLE_PROPERTIES.get(key, {})
        if not isinstance(meta, dict) or "file" not in meta:
            return False
        file_key = meta["file"]
        dotted_path = meta["path"]
        data = _yaml_read(file_key)
        if not data:
            return False
        # Get current value for type inference
        current = _yaml_get(data, dotted_path)
        typed_value = _coerce_yaml_value(value, current)
        _yaml_set(data, dotted_path, typed_value)
        return _yaml_write(file_key, data)

    # ── Templates ──

    def apply_template(self, template_name: str) -> Dict:
        """Apply a predefined config template.

        Silently skips properties whose config files don't exist
        (e.g. Paper YAML settings when running Forge).
        """
        template = TEMPLATES.get(template_name)
        if not template:
            return {"error": f"Шаблон '{template_name}' не найден."}

        # New-style template with 'properties' dict
        if "properties" in template:
            changes = {}
            skipped = 0
            for prop_key, val in template["properties"].items():
                ok = self.write_property(prop_key, val)
                if ok:
                    meta = EDITABLE_PROPERTIES.get(prop_key, {})
                    desc = meta.get("desc", prop_key) if isinstance(meta, dict) else prop_key
                    changes[desc] = val
                else:
                    skipped += 1
            if skipped:
                changes["⚠ Пропущено (нет файла)"] = f"{skipped} настр."
            return changes

        # Old-style template (server.properties only)
        changes = {}
        for key, val in template.items():
            if key in ("label", "desc"):
                continue
            self.write_property(key, val)
            changes[key] = val
        return changes

    # ── Summary ──

    def get_editable_summary(self) -> str:
        """Get formatted summary of editable properties (server.properties only)."""
        props = self.read_properties()
        lines = []
        for key, meta in EDITABLE_PROPERTIES.items():
            # Only show server.properties keys in the simple summary
            if isinstance(meta, dict) and "file" in meta:
                continue
            val = props.get(key, "не задано")
            lines.append(f"<code>{key}</code> = {val}")
        return "\n".join(lines)


server_config = ServerConfig()
