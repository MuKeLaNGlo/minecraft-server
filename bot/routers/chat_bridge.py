import json

from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import Message

from db.database import db
from minecraft.docker_manager import docker_manager
from minecraft.rcon import rcon
from utils.logger import logger


class ChatBridgeFilter(BaseFilter):
    """Only match text messages from the configured bridge chat."""

    async def __call__(self, message: Message) -> bool:
        if not message.text or message.text.startswith("/"):
            return False
        if message.from_user and message.from_user.is_bot:
            return False
        if await db.get_setting("chat_bridge_enabled") != "1":
            return False
        chat_id = await db.get_setting("notifications_chat_id")
        if not chat_id:
            return False
        return str(message.chat.id) == chat_id


chat_bridge_router = Router()


@chat_bridge_router.message(ChatBridgeFilter())
async def forward_to_mc(message: Message):
    """Forward Telegram group messages to Minecraft server."""
    if not await docker_manager.is_running():
        return

    sender = message.from_user.full_name or "Telegram"
    text = message.text

    tellraw_json = json.dumps([
        {"text": "[TG] ", "color": "blue"},
        {"text": sender, "color": "aqua"},
        {"text": f": {text}", "color": "white"},
    ])
    try:
        await rcon.execute(f"tellraw @a {tellraw_json}")
    except Exception as e:
        logger.warning(f"Chat bridge TG->MC error: {e}")
