from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from db.database import db
from services.scheduler import add_task, remove_task, toggle_task
from states.states import SchedulerState
from utils.formatting import section_header, success_text
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

scheduler_router = Router()

SCHEDULER_MENU_TEXT = section_header(
    "⏰", "Планировщик",
    "Автоматические задачи: бэкапы, рестарты и RCON-команды по расписанию (cron).",
)

_scheduler_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список задач", callback_data="sch:list")],
        [InlineKeyboardButton(text="➕ Добавить задачу", callback_data="sch:add")],
        back_row("main"),
    ]
)

_task_types = {
    "backup": "💾 Бэкап",
    "restart": "🔄 Рестарт",
    "command": "🎮 RCON команда",
}


@scheduler_router.callback_query(F.data == "nav:scheduler")
async def scheduler_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await show_menu(callback, SCHEDULER_MENU_TEXT, _scheduler_kb)
    await callback.answer()


@scheduler_router.callback_query(F.data.startswith("sch:"))
async def scheduler_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "list":
        await callback.answer()
        tasks = await db.get_scheduled_tasks()
        if not tasks:
            await show_menu(callback, "Задач нет.", _scheduler_kb)
            return

        buttons = []
        for task in tasks:
            task_id, task_type, cron_expr, enabled, extra_data, _ = task
            status = "✅" if enabled else "❌"
            label = _task_types.get(task_type, task_type)
            extra = f" ({extra_data})" if extra_data else ""
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {label}: {cron_expr}{extra}",
                    callback_data=f"sch:detail:{task_id}",
                )
            ])
        buttons.append(back_row("scheduler"))
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, "📋 Запланированные задачи:", kb)

    elif action == "detail":
        task_id = int(parts[2])
        await callback.answer()
        detail_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Вкл", callback_data=f"sch:enable:{task_id}"),
                    InlineKeyboardButton(text="❌ Выкл", callback_data=f"sch:disable:{task_id}"),
                ],
                [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"sch:delete:{task_id}")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="sch:list")],
            ]
        )
        await show_menu(callback, f"Задача #{task_id}", detail_kb)

    elif action == "enable":
        task_id = int(parts[2])
        await callback.answer("Включено")
        await toggle_task(task_id, True)
        logger.info(f"Task {task_id} enabled by {callback.from_user.id}")
        await show_menu(callback, success_text(f"Задача #{task_id} включена."), _scheduler_kb)

    elif action == "disable":
        task_id = int(parts[2])
        await callback.answer("Выключено")
        await toggle_task(task_id, False)
        logger.info(f"Task {task_id} disabled by {callback.from_user.id}")
        await show_menu(callback, success_text(f"Задача #{task_id} выключена."), _scheduler_kb)

    elif action == "delete":
        task_id = int(parts[2])
        await callback.answer("Удалено")
        await remove_task(task_id)
        logger.info(f"Task {task_id} deleted by {callback.from_user.id}")
        await show_menu(callback, success_text(f"Задача #{task_id} удалена."), _scheduler_kb)

    elif action == "add":
        await callback.answer()
        type_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💾 Бэкап", callback_data="sch:type:backup")],
                [InlineKeyboardButton(text="🔄 Рестарт", callback_data="sch:type:restart")],
                [InlineKeyboardButton(text="🎮 RCON команда", callback_data="sch:type:command")],
                back_row("scheduler"),
            ]
        )
        await show_menu(callback, "Выбери тип задачи:", type_kb)

    elif action == "type":
        task_type = parts[2]
        await callback.answer()
        await state.update_data(task_type=task_type)

        if task_type == "command":
            await state.set_state(SchedulerState.waiting_extra)
            await callback.message.answer(
                "Введи RCON команду для выполнения по расписанию:",
                reply_markup=CANCEL_REPLY_KB,
            )
        else:
            await state.set_state(SchedulerState.waiting_cron)
            await callback.message.answer(
                "Введи cron-выражение (5 полей):\n"
                "<code>минуты часы день_месяца месяц день_недели</code>\n\n"
                "Примеры:\n"
                "  <code>0 */6 * * *</code> — каждые 6 часов\n"
                "  <code>0 4 * * *</code> — ежедневно в 4:00\n"
                "  <code>0 0 * * 0</code> — каждое воскресенье",
                reply_markup=CANCEL_REPLY_KB,
            )

    elif action in ("back", "scheduler"):
        await callback.answer()
        await show_menu(callback, SCHEDULER_MENU_TEXT, _scheduler_kb)


@scheduler_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(SchedulerState.waiting_cron, SchedulerState.waiting_extra),
)
async def cancel_scheduler(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@scheduler_router.message(StateFilter(SchedulerState.waiting_extra))
async def process_extra_data(message: Message, state: FSMContext):
    extra_data = message.text.strip()
    await state.update_data(extra_data=extra_data)
    await state.set_state(SchedulerState.waiting_cron)
    await message.answer(
        "Теперь введи cron-выражение:\n"
        "<code>минуты часы день_месяца месяц день_недели</code>\n\n"
        "Пример: <code>0 */6 * * *</code> — каждые 6 часов",
        reply_markup=CANCEL_REPLY_KB,
    )


@scheduler_router.message(StateFilter(SchedulerState.waiting_cron))
async def process_cron(message: Message, state: FSMContext):
    cron_expr = message.text.strip()

    cron_parts = cron_expr.split()
    if len(cron_parts) != 5:
        await message.answer(
            "Неверный формат. Нужно 5 полей: минуты часы день месяц день_недели.\n"
            "Попробуй ещё раз:"
        )
        return

    from apscheduler.triggers.cron import CronTrigger
    try:
        CronTrigger.from_crontab(cron_expr)
    except ValueError as e:
        await message.answer(f"Ошибка в cron-выражении: {e}\nПопробуй ещё раз:")
        return

    data = await state.get_data()
    task_type = data.get("task_type")
    extra_data = data.get("extra_data")

    task_id = await add_task(task_type, cron_expr, extra_data)
    logger.info(f"Task {task_id} created by {message.from_user.id}: {task_type} {cron_expr}")

    label = _task_types.get(task_type, task_type)
    extra_info = f"\nКоманда: {extra_data}" if extra_data else ""

    await state.clear()
    await message.answer(
        success_text(
            f"Задача создана!\n"
            f"Тип: {label}\n"
            f"Расписание: <code>{cron_expr}</code>{extra_info}"
        )
    )
    await message.answer(SCHEDULER_MENU_TEXT, reply_markup=_scheduler_kb, parse_mode="HTML")
