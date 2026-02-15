import asyncio
import traceback
from datetime import datetime, timezone

from aiogram.types import ErrorEvent

from core.config import config
from core.loader import bot, dp
from db.database import db
from utils.logger import logger

# Routers
from routers.admin import admin_router
from routers.server import server_router
from routers.players import players_router
from routers.mods import mods_router
from routers.plugins import plugins_router
from routers.backups import backups_router
from routers.config_editor import config_router
from routers.monitoring import monitoring_router
from routers.scheduler import scheduler_router
from routers.console import console_router
from routers.worlds import worlds_router
from routers.stats import stats_router
from routers.chat_bridge import chat_bridge_router
from routers.bot_settings import bot_settings_router
from routers.common import common_router

# Services
from services.monitoring import monitoring
from services.modrinth import modrinth
from services.scheduler import init_scheduler, scheduler
from services.log_watcher import log_watcher, LogEvent
from minecraft.docker_manager import docker_manager


async def on_startup() -> None:
    await db.connect()

    # Auto-add super admin from env
    if config.super_admin_id:
        admin_id = str(config.super_admin_id)
        if not await db.check_admin(admin_id):
            await db.add_admin(admin_id)
            logger.info(f"Супер-админ {admin_id} добавлен из переменных окружения")

    # Replay missed logs from bot downtime — recover join/leave events.
    # This must happen BEFORE LogWatcher starts to avoid duplicates.
    replay_since = None
    last_shutdown = await db.get_setting("bot_last_shutdown")
    if last_shutdown:
        replay_since = datetime.fromisoformat(last_shutdown).replace(tzinfo=timezone.utc)
    elif await docker_manager.is_running():
        # First run — replay from MC server container start
        try:
            status = await docker_manager.status()
            started_at = status.get("started_at", "")
            if started_at:
                # Docker format: "2024-01-15T12:34:56.789Z"
                replay_since = datetime.fromisoformat(
                    started_at.replace("Z", "+00:00")
                )
                logger.info(f"First run — will replay logs from MC start: {started_at}")
        except Exception:
            pass

    if replay_since and await docker_manager.is_running():
        try:
            events = await log_watcher.replay_missed_logs(replay_since)
            if events:
                # Close stale sessions at shutdown time (not now!) so replay
                # can correctly re-open/close them with real timestamps.
                close_at = last_shutdown or replay_since.strftime("%Y-%m-%d %H:%M:%S")
                await db.close_all_sessions(at=close_at)
                for etype, pname, ts in events:
                    if etype == "join":
                        await db.open_session_at(pname, ts)
                    elif etype == "leave":
                        await db.close_session_at(pname, ts)
                logger.info(f"Replayed {len(events)} session events "
                            f"(since {replay_since.strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                await db.close_all_sessions()
        except Exception as e:
            logger.warning(f"Log replay failed: {e}")
            await db.close_all_sessions()
    else:
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
        except Exception as e:
            logger.warning(f"Notification send failed: {e}")

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
        except Exception as e:
            logger.warning(f"Notification send failed: {e}")

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
        except Exception as e:
            logger.warning(f"Notification send failed: {e}")

    async def _close_stale_sessions(event: LogEvent):
        """Close all open sessions when MC server starts/restarts.

        Handles all scenarios:
        - Server restarted via bot
        - Server restarted manually / via docker
        - VM/physical server crash + restart
        Any session still open when server boots is stale.
        """
        closed = await db.close_all_sessions()
        logger.info(f"Server ready — closed all stale player sessions")

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
        except Exception as e:
            logger.warning(f"Notification send failed: {e}")

    log_watcher.on("join", _notify_join)
    log_watcher.on("leave", _notify_leave)
    log_watcher.on("chat", _bridge_mc_to_tg)
    log_watcher.on("server_ready", _close_stale_sessions)
    log_watcher.on("server_ready", _notify_server_ready)

    await log_watcher.start(interval=config.log_watcher_interval)

    # Safety net: ensure currently online players have open sessions.
    # Log replay above should handle this, but /list catches edge cases.
    # open_session() won't duplicate if session already exists.
    try:
        from minecraft.player_manager import player_manager
        if await docker_manager.is_running():
            data = await player_manager.get_online_players()
            for name in data.get("players", []):
                await db.open_session(name)
                logger.info(f"Recovered session for online player: {name}")
            if data.get("players"):
                logger.info(f"Synced {len(data['players'])} online player(s) on startup")
    except Exception as e:
        logger.warning(f"Failed to sync online players on startup: {e}")

    logger.info("Бот запущен")


async def on_shutdown() -> None:
    # Save shutdown time so next startup can replay missed logs
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        await db.set_setting("bot_last_shutdown", now)
    except Exception:
        pass
    await log_watcher.stop()
    await monitoring.stop()
    scheduler.shutdown(wait=False)
    await modrinth.close()
    await db.disconnect()
    logger.info("Бот остановлен")


_last_error_notify: float = 0


@dp.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    """Catch unhandled exceptions and notify super admin."""
    global _last_error_notify
    exc = event.exception
    logger.error(f"Unhandled exception: {exc}", exc_info=exc)

    if not config.super_admin_id:
        return True

    # Rate limit: max 1 error message per 60 seconds
    import time
    now = time.monotonic()
    if now - _last_error_notify < 60:
        return True
    _last_error_notify = now

    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_short = "".join(tb[-3:])[:1500]

    update_info = ""
    if event.update and event.update.message:
        uid = event.update.message.from_user.id
        update_info = f"\nUser: <code>{uid}</code>"
    elif event.update and event.update.callback_query:
        uid = event.update.callback_query.from_user.id
        data = event.update.callback_query.data
        update_info = f"\nUser: <code>{uid}</code>\nCallback: <code>{data}</code>"

    text = (
        f"🚨 <b>Ошибка в боте</b>\n\n"
        f"<code>{type(exc).__name__}: {str(exc)[:300]}</code>"
        f"{update_info}\n\n"
        f"<pre>{tb_short}</pre>"
    )
    try:
        await bot.send_message(config.super_admin_id, text)
    except Exception as e:
        logger.warning(f"Failed to notify admin about error: {e}")

    return True


async def main() -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Include routers (order: specific first, catch-all last)
    dp.include_router(admin_router)
    dp.include_router(bot_settings_router)
    dp.include_router(server_router)
    dp.include_router(players_router)
    dp.include_router(mods_router)
    dp.include_router(plugins_router)
    dp.include_router(backups_router)
    dp.include_router(config_router)
    dp.include_router(monitoring_router)
    dp.include_router(scheduler_router)
    dp.include_router(console_router)
    dp.include_router(worlds_router)
    dp.include_router(stats_router)
    dp.include_router(chat_bridge_router)
    dp.include_router(common_router)  # last — catch-all /start + nav:main

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
