import logging
from logging.handlers import RotatingFileHandler

from core.config import config

logger = logging.getLogger("mc-bot")
logger.setLevel(logging.INFO)

# File handler
file_handler = RotatingFileHandler(
    "/bot-data/bot.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=2,
    encoding="utf-8",
)
file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler (for docker logs)
console_handler = logging.StreamHandler()
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)


async def log_to_group(bot, text: str) -> None:
    """Send log message to Telegram group if configured."""
    if config.log_chat_id:
        try:
            await bot.send_message(config.log_chat_id, text)
        except Exception as e:
            logger.warning(f"Failed to send log to group chat: {e}")
