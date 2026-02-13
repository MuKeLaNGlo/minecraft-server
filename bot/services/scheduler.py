import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from db.database import db
from utils.logger import logger

scheduler = AsyncIOScheduler()


async def init_scheduler():
    """Load saved tasks from DB and register them."""
    tasks = await db.get_scheduled_tasks()
    for task in tasks:
        task_id, task_type, cron_expr, enabled, extra_data, _ = task
        if not enabled:
            continue
        _add_job(task_id, task_type, cron_expr, extra_data)
    scheduler.start()
    logger.info(f"Scheduler started with {len(tasks)} tasks")


def _add_job(task_id: int, task_type: str, cron_expr: str, extra_data: str = None):
    """Add a job to the scheduler."""
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
    except ValueError as e:
        logger.error(f"Invalid cron expression for task {task_id}: {e}")
        return

    job_id = f"task_{task_id}"

    if task_type == "backup":
        async def _backup():
            from minecraft.backup_manager import backup_manager
            result = await backup_manager.create_backup()
            if result["success"]:
                logger.info(f"Scheduled backup created: {result['filename']}")
                # Rotate after scheduled backup
                await backup_manager.rotate_backups(keep=10)
            else:
                logger.error(f"Scheduled backup failed: {result.get('error')}")

        scheduler.add_job(_backup, trigger, id=job_id, replace_existing=True)

    elif task_type == "restart":
        async def _restart():
            from minecraft.rcon import rcon
            from minecraft.docker_manager import docker_manager
            await rcon.execute("say Сервер перезапускается через 1 минуту!")
            await asyncio.sleep(50)
            await rcon.execute("say Сервер перезапускается через 10 секунд!")
            await asyncio.sleep(10)
            await docker_manager.restart()
            logger.info("Scheduled restart executed")

        scheduler.add_job(_restart, trigger, id=job_id, replace_existing=True)

    elif task_type == "command":
        async def _command():
            from minecraft.rcon import rcon
            if extra_data:
                result = await rcon.execute(extra_data)
                logger.info(f"Scheduled command: {extra_data} -> {result[:100]}")

        scheduler.add_job(_command, trigger, id=job_id, replace_existing=True)


async def add_task(task_type: str, cron_expr: str, extra_data: str = None) -> int:
    """Add a new scheduled task to DB and scheduler."""
    task_id = await db.add_scheduled_task(task_type, cron_expr, extra_data)
    _add_job(task_id, task_type, cron_expr, extra_data)
    return task_id


async def remove_task(task_id: int):
    """Remove a scheduled task from DB and scheduler."""
    job_id = f"task_{task_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    await db.remove_scheduled_task(task_id)


async def toggle_task(task_id: int, enabled: bool):
    """Enable or disable a scheduled task."""
    await db.toggle_scheduled_task(task_id, enabled)
    job_id = f"task_{task_id}"
    if enabled:
        # Re-add the job
        tasks = await db.get_scheduled_tasks()
        for task in tasks:
            if task[0] == task_id:
                _add_job(task_id, task[1], task[2], task[4])
                break
    else:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
