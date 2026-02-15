import time
from typing import Annotated

import jwt
from aiogram.utils.web_app import safe_parse_webapp_init_data
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from core.config import config
from db.database import db

_ALGORITHM = "HS256"
_TOKEN_TTL = 86400  # 24 hours

ROLE_LEVELS = {
    "public": 0,
    "user": 1,
    "admin": 2,
    "super_admin": 3,
}


class AuthRequest(BaseModel):
    init_data: str


class AuthResponse(BaseModel):
    token: str
    role: str
    telegram_id: int
    first_name: str


class CurrentUser(BaseModel):
    telegram_id: int
    role: str


async def _resolve_role(telegram_id: int) -> str:
    tid = str(telegram_id)
    if config.super_admin_id and telegram_id == config.super_admin_id:
        return "super_admin"
    if await db.check_admin(tid):
        return "admin"
    if await db.user_exists(tid):
        return "user"
    return "public"


async def authenticate(body: AuthRequest) -> AuthResponse:
    try:
        data = safe_parse_webapp_init_data(
            token=config.bot_token, init_data=body.init_data
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid init data")

    user = data.user
    if not user:
        raise HTTPException(status_code=401, detail="No user in init data")

    role = await _resolve_role(user.id)

    payload = {
        "tid": user.id,
        "role": role,
        "exp": int(time.time()) + _TOKEN_TTL,
    }
    token = jwt.encode(payload, config.jwt_secret, algorithm=_ALGORITHM)

    return AuthResponse(
        token=token,
        role=role,
        telegram_id=user.id,
        first_name=user.first_name or "",
    )


def _decode_token(authorization: str) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return CurrentUser(telegram_id=payload["tid"], role=payload["role"])


async def get_current_user(
    authorization: Annotated[str, Header()],
) -> CurrentUser:
    return _decode_token(authorization)


def require_role(min_role: str):
    min_level = ROLE_LEVELS.get(min_role, 0)

    async def dependency(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        level = ROLE_LEVELS.get(user.role, 0)
        if level < min_level:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return Depends(dependency)
