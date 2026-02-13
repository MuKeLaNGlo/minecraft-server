from pathlib import Path
from typing import Dict, Optional

from core.config import config


# Property metadata: type determines UI in config_editor
# Types: bool, enum, range, text
EDITABLE_PROPERTIES = {
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
        "presets": [("4", "🐢 4"), ("6", "6"), ("10", "⚙ 10"), ("16", "🚀 16"), ("24", "🔭 24")],
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
}

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
}

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


class ServerConfig:
    def __init__(self):
        self.path = Path(config.mc_data_path) / "server.properties"

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
        props = self.read_properties()
        return props.get(key)

    def write_property(self, key: str, value: str) -> bool:
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

    def apply_template(self, template_name: str) -> Dict:
        """Apply a predefined config template."""
        template = TEMPLATES.get(template_name)
        if not template:
            return {"error": f"Шаблон '{template_name}' не найден."}
        changes = {}
        for key, val in template.items():
            if key in ("label", "desc"):
                continue
            self.write_property(key, val)
            changes[key] = val
        return changes

    def get_editable_summary(self) -> str:
        """Get formatted summary of editable properties."""
        props = self.read_properties()
        lines = []
        for key, meta in EDITABLE_PROPERTIES.items():
            val = props.get(key, "не задано")
            lines.append(f"<code>{key}</code> = {val}")
        return "\n".join(lines)


server_config = ServerConfig()
