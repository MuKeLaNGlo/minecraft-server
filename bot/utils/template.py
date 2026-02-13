import json
import os
from pathlib import Path
from typing import Any, Dict, List

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from jinja2 import Environment, FileSystemLoader

_BOT_DIR = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _BOT_DIR / "templates"


def render_template(
    template_name: str,
    root: str = "messages",
    **context: Any,
) -> str:
    """Render a Jinja2 template from templates/<root>/."""
    template_dir = str(_TEMPLATES_DIR / root)
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(**context)


def load_keyboards(json_filename: str) -> Dict[str, ReplyKeyboardMarkup]:
    """Load keyboard definitions from templates/keyboards/<json_filename>."""
    filepath = _TEMPLATES_DIR / "keyboards" / json_filename
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    keyboards = {}
    for name, params in data.items():
        if "keyboard" not in params:
            continue
        buttons = [
            [KeyboardButton(text=btn) for btn in row] for row in params["keyboard"]
        ]
        keyboards[name] = ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=params.get("resize_keyboard", True),
        )
    return keyboards


def load_valid_commands(json_filename: str) -> Dict[str, List[str]]:
    """Load valid command mappings from templates/commands/<json_filename>."""
    filepath = _TEMPLATES_DIR / "commands" / json_filename
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("valid_commands", {})
