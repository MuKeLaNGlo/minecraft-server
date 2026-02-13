import asyncio

from core.config import config
from core.loader import bot, dp
from db.database import db
from utils.logger import logger

# Routers
from routers.admin import admin_router
from routers.server import server_router
from routers.players import players_router
from routers.mods import mods_router
from routers.backups import backups_router
from routers.config_editor import config_router
from routers.monitoring import monitoring_router
from routers.scheduler import scheduler_router
from routers.console import console_router
from routers.worlds import worlds_router
from routers.chat_bridge import chat_bridge_router
from routers.bot_settings import bot_settings_router
from routers.common import common_router

# Services
from services.monitoring import monitoring
from services.modrinth import modrinth
from services.scheduler import init_scheduler, scheduler
from services.log_watcher import log_watcher, LogEvent


async def on_startup() -> None:
    await db.connect()

    # Auto-add super admin from env
    if config.super_admin_id:
        admin_id = str(config.super_admin_id)
        if not await db.check_admin(admin_id):
            await db.add_admin(admin_id)
            logger.info(f"Супер-админ {admin_id} добавлен из переменных окружения")

    # Close stale player sessions from previous run
    await db.close_all_sessions()

    # Start scheduler
    await init_scheduler()

    # Start monitoring
    alert_ids = [str(config.super_admin_id)] if config.super_admin_id else []
    await monitoring.start(bot, alert_ids, interval=60)

    # Configure LogWatcher handlers

    # Session tracking (always active)
    async def _session_open(event: LogEvent):
        logger.info(f"Player joined: {event.player_name}")
        await db.open_session(event.player_name)

    async def _session_close(event: LogEvent):
        logger.info(f"Player left: {event.player_name}")
        await db.close_session(event.player_name)

    log_watcher.on("join", _session_open)
    log_watcher.on("leave", _session_close)

    # Notifications — always registered, check DB at runtime
    async def _notify_join(event: LogEvent):
        if await db.get_setting("notifications_enabled") != "1":
            return
        chat_id = await db.get_setting("notifications_chat_id")
        if not chat_id:
            return
        try:
            await bot.send_message(
                chat_id, f"🟢 <b>{event.player_name}</b> зашёл на сервер"
            )
        except Exception:
            pass

    async def _notify_leave(event: LogEvent):
        if await db.get_setting("notifications_enabled") != "1":
            return
        chat_id = await db.get_setting("notifications_chat_id")
        if not chat_id:
            return
        try:
            await bot.send_message(
                chat_id, f"🔴 <b>{event.player_name}</b> вышел с сервера"
            )
        except Exception:
            pass

    async def _bridge_mc_to_tg(event: LogEvent):
        if await db.get_setting("chat_bridge_enabled") != "1":
            return
        chat_id = await db.get_setting("notifications_chat_id")
        if not chat_id:
            return
        try:
            await bot.send_message(
                chat_id, f"💬 <b>{event.player_name}</b>: {event.message}"
            )
        except Exception:
            pass

    async def _notify_server_ready(event: LogEvent):
        if await db.get_setting("notifications_enabled") != "1":
            return
        chat_id = await db.get_setting("notifications_chat_id")
        if not chat_id:
            return
        try:
            secs = event.message or "?"
            await bot.send_message(
                chat_id, f"✅ Сервер запущен и готов к игре! ({secs}s)"
            )
        except Exception:
            pass

    log_watcher.on("join", _notify_join)
    log_watcher.on("leave", _notify_leave)
    log_watcher.on("chat", _bridge_mc_to_tg)
    log_watcher.on("server_ready", _notify_server_ready)

    await log_watcher.start(interval=config.log_watcher_interval)

    logger.info("Бот запущен")


async def on_shutdown() -> None:
    await log_watcher.stop()
    await monitoring.stop()
    scheduler.shutdown(wait=False)
    await modrinth.close()
    await db.disconnect()
    logger.info("Бот остановлен")


async def main() -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Include routers (order: specific first, catch-all last)
    dp.include_router(admin_router)
    dp.include_router(bot_settings_router)
    dp.include_router(server_router)
    dp.include_router(players_router)
    dp.include_router(mods_router)
    dp.include_router(backups_router)
    dp.include_router(config_router)
    dp.include_router(monitoring_router)
    dp.include_router(scheduler_router)
    dp.include_router(console_router)
    dp.include_router(worlds_router)
    dp.include_router(chat_bridge_router)
    dp.include_router(common_router)  # last — catch-all /start + nav:main

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
