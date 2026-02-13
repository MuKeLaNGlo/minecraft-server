from typing import List

from aiogram.filters import BaseFilter
from aiogram.types import Message

from db.database import db


class TextInFilter(BaseFilter):
    """Check if message text matches any string in list (case-insensitive)."""

    def __init__(self, texts: List[str]):
        self.texts = [t.lower() for t in texts]

    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        return message.text.lower() in self.texts


class IsAdminFilter(BaseFilter):
    """Check if user is admin."""

    async def __call__(self, message: Message) -> bool:
        return await db.check_admin(str(message.from_user.id))
