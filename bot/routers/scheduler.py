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
    "Автоматические задачи: бэкапы, рестарты\nи RCON-команды по расписанию.",
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

# --- Schedule presets ---
# (callback_suffix, label, cron_expression, human_readable)
_INTERVAL_PRESETS = [
    ("1h", "⏱ Каждый час", "0 */1 * * *", "каждый час"),
    ("2h", "⏱ Каждые 2 часа", "0 */2 * * *", "каждые 2 часа"),
    ("4h", "⏱ Каждые 4 часа", "0 */4 * * *", "каждые 4 часа"),
    ("6h", "⏱ Каждые 6 часов", "0 */6 * * *", "каждые 6 часов"),
    ("12h", "⏱ Каждые 12 часов", "0 */12 * * *", "каждые 12 часов"),
]

_DAILY_PRESETS = [
    ("00", "🌙 00:00", "0 0 * * *", "ежедневно в 00:00"),
    ("04", "🌅 04:00", "0 4 * * *", "ежедневно в 04:00"),
    ("06", "☀ 06:00", "0 6 * * *", "ежедневно в 06:00"),
    ("12", "🕐 12:00", "0 12 * * *", "ежедневно в 12:00"),
    ("18", "🌆 18:00", "0 18 * * *", "ежедневно в 18:00"),
    ("22", "🌙 22:00", "0 22 * * *", "ежедневно в 22:00"),
]

_WEEKLY_PRESETS = [
    ("mon", "Пн", "0 4 * * 1"),
    ("wed", "Ср", "0 4 * * 3"),
    ("fri", "Пт", "0 4 * * 5"),
    ("sat", "Сб", "0 4 * * 6"),
    ("sun", "Вс", "0 4 * * 0"),
]

# Build lookup: suffix -> cron expression
_ALL_PRESETS = {}
for suffix, _, cron, _ in _INTERVAL_PRESETS:
    _ALL_PRESETS[suffix] = cron
for suffix, _, cron, _ in _DAILY_PRESETS:
    _ALL_PRESETS[f"d{suffix}"] = cron
for suffix, _, cron in _WEEKLY_PRESETS:
    _ALL_PRESETS[f"w{suffix}"] = cron


def _cron_to_human(cron: str) -> str:
    """Convert cron expression to human-readable Russian string."""
    parts = cron.split()
    if len(parts) != 5:
        return cron
    minute, hour, dom, month, dow = parts

    # Check interval presets
    for _, _, c, h in _INTERVAL_PRESETS:
        if c == cron:
            return h
    for _, _, c, h in _DAILY_PRESETS:
        if c == cron:
            return h

    # Weekly
    dow_names = {"0": "Вс", "1": "Пн", "2": "Вт", "3": "Ср", "4": "Чт", "5": "Пт", "6": "Сб", "7": "Вс"}
    if dom == "*" and month == "*" and dow != "*":
        day_label = dow_names.get(dow, dow)
        return f"по {day_label} в {hour.zfill(2)}:{minute.zfill(2)}"

    # Daily
    if dom == "*" and month == "*" and dow == "*":
        if hour.startswith("*/"):
            return f"каждые {hour[2:]}ч"
        return f"ежедневно в {hour.zfill(2)}:{minute.zfill(2)}"

    return cron


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
            schedule = _cron_to_human(cron_expr)
            extra = f" ({extra_data})" if extra_data else ""
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {label}: {schedule}{extra}",
                    callback_data=f"sch:detail:{task_id}",
                )
            ])
        buttons.append(back_row("scheduler"))
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, "📋 Запланированные задачи:", kb)

    elif action == "detail":
        task_id = int(parts[2])
        await callback.answer()
        task = await _get_task(task_id)
        if not task:
            await show_menu(callback, "Задача не найдена.", _scheduler_kb)
            return
        task_id, task_type, cron_expr, enabled, extra_data, created = task
        label = _task_types.get(task_type, task_type)
        status = "✅ Включена" if enabled else "❌ Выключена"
        schedule = _cron_to_human(cron_expr)
        extra_line = f"\nКоманда: <code>{extra_data}</code>" if extra_data else ""

        text = (
            f"<b>Задача #{task_id}</b>\n\n"
            f"Тип: {label}\n"
            f"Расписание: {schedule}\n"
            f"Cron: <code>{cron_expr}</code>\n"
            f"Статус: {status}{extra_line}"
        )
        toggle_text = "❌ Выключить" if enabled else "✅ Включить"
        toggle_cb = f"sch:disable:{task_id}" if enabled else f"sch:enable:{task_id}"
        detail_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=toggle_text, callback_data=toggle_cb)],
                [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"sch:delete:{task_id}")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="sch:list")],
            ]
        )
        await show_menu(callback, text, detail_kb)

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
        await callback.answer()
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"sch:confirm_delete:{task_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"sch:detail:{task_id}"),
            ],
        ])
        await show_menu(callback, f"Удалить задачу <b>#{task_id}</b>?", confirm_kb)

    elif action == "confirm_delete":
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
            # Show schedule constructor
            await _show_schedule_mode(callback, state)

    elif action == "freq":
        # Schedule mode selection
        freq = parts[2]
        await callback.answer()

        if freq == "interval":
            buttons = []
            row = []
            for suffix, label, cron, _ in _INTERVAL_PRESETS:
                row.append(InlineKeyboardButton(text=label, callback_data=f"sch:pick:{suffix}"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="sch:freq_back")])
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await show_menu(callback, "⏱ <b>Выбери интервал:</b>", kb)

        elif freq == "daily":
            buttons = []
            row = []
            for suffix, label, cron, _ in _DAILY_PRESETS:
                row.append(InlineKeyboardButton(text=label, callback_data=f"sch:pick:d{suffix}"))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton(text="✏ Своё время", callback_data="sch:custom_time")])
            buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="sch:freq_back")])
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await show_menu(callback, "📅 <b>Ежедневно — выбери время:</b>", kb)

        elif freq == "weekly":
            buttons = []
            row = []
            for suffix, label, cron in _WEEKLY_PRESETS:
                row.append(InlineKeyboardButton(text=label, callback_data=f"sch:pick:w{suffix}"))
            buttons.append(row)
            buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="sch:freq_back")])
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await show_menu(
                callback,
                "📆 <b>Еженедельно — выбери день:</b>\n"
                "<i>Выполнение в 04:00</i>",
                kb,
            )

        elif freq == "cron":
            await state.set_state(SchedulerState.waiting_cron)
            await callback.message.answer(
                "Введи cron-выражение (5 полей):\n"
                "<code>минуты часы день_месяца месяц день_недели</code>\n\n"
                "Примеры:\n"
                "  <code>0 */6 * * *</code> — каждые 6 часов\n"
                "  <code>0 4 * * *</code> — ежедневно в 4:00\n"
                "  <code>30 3 * * 1,5</code> — Пн и Пт в 3:30",
                reply_markup=CANCEL_REPLY_KB,
            )

    elif action == "custom_time":
        await callback.answer()
        await state.set_state(SchedulerState.waiting_time)
        await callback.message.answer(
            "Введи время в формате <b>ЧЧ:ММ</b>\n"
            "Например: <code>04:30</code> или <code>18:00</code>",
            reply_markup=CANCEL_REPLY_KB,
        )

    elif action == "pick":
        preset_key = parts[2]
        cron_expr = _ALL_PRESETS.get(preset_key)
        if not cron_expr:
            await callback.answer("Пресет не найден")
            return
        await callback.answer()
        await _create_task(callback, state, cron_expr)

    elif action == "freq_back":
        await callback.answer()
        await _show_schedule_mode(callback, state)

    elif action in ("back", "scheduler"):
        await callback.answer()
        await show_menu(callback, SCHEDULER_MENU_TEXT, _scheduler_kb)


async def _get_task(task_id: int):
    """Get a single task by ID from DB."""
    tasks = await db.get_scheduled_tasks()
    for task in tasks:
        if task[0] == task_id:
            return task
    return None


async def _show_schedule_mode(event, state: FSMContext):
    """Show schedule frequency selection menu."""
    data = await state.get_data()
    task_type = data.get("task_type", "")
    label = _task_types.get(task_type, task_type)

    text = (
        f"<b>Расписание для: {label}</b>\n\n"
        "Выбери частоту:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Каждые N часов", callback_data="sch:freq:interval")],
        [InlineKeyboardButton(text="📅 Ежедневно", callback_data="sch:freq:daily")],
        [InlineKeyboardButton(text="📆 Еженедельно", callback_data="sch:freq:weekly")],
        [InlineKeyboardButton(text="⌨ Ввести cron вручную", callback_data="sch:freq:cron")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="sch:add")],
    ])
    await show_menu(event, text, kb)


async def _create_task(callback: CallbackQuery, state: FSMContext, cron_expr: str):
    """Finalize task creation with the given cron expression."""
    data = await state.get_data()
    task_type = data.get("task_type")
    extra_data = data.get("extra_data")

    task_id = await add_task(task_type, cron_expr, extra_data)
    logger.info(f"Task {task_id} created by {callback.from_user.id}: {task_type} {cron_expr}")

    label = _task_types.get(task_type, task_type)
    schedule = _cron_to_human(cron_expr)
    extra_info = f"\nКоманда: <code>{extra_data}</code>" if extra_data else ""

    await state.clear()
    await show_menu(
        callback,
        success_text(
            f"Задача создана!\n\n"
            f"Тип: {label}\n"
            f"Расписание: {schedule}\n"
            f"Cron: <code>{cron_expr}</code>{extra_info}"
        ),
        _scheduler_kb,
    )


@scheduler_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(
        SchedulerState.waiting_cron,
        SchedulerState.waiting_extra,
        SchedulerState.waiting_time,
    ),
)
async def cancel_scheduler(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@scheduler_router.message(StateFilter(SchedulerState.waiting_extra))
async def process_extra_data(message: Message, state: FSMContext):
    extra_data = message.text.strip()
    await state.update_data(extra_data=extra_data)
    # Show schedule constructor for command too
    text = (
        f"<b>Расписание для: 🎮 RCON команда</b>\n"
        f"Команда: <code>{extra_data}</code>\n\n"
        "Выбери частоту:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Каждые N часов", callback_data="sch:freq:interval")],
        [InlineKeyboardButton(text="📅 Ежедневно", callback_data="sch:freq:daily")],
        [InlineKeyboardButton(text="📆 Еженедельно", callback_data="sch:freq:weekly")],
        [InlineKeyboardButton(text="⌨ Ввести cron вручную", callback_data="sch:freq:cron")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="sch:add")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(None)  # exit FSM, continue with callbacks


@scheduler_router.message(StateFilter(SchedulerState.waiting_time))
async def process_custom_time(message: Message, state: FSMContext):
    """Handle custom time input like HH:MM."""
    text = message.text.strip()
    # Parse HH:MM
    import re
    match = re.match(r"^(\d{1,2})[:\.](\d{2})$", text)
    if not match:
        await message.answer("Неверный формат. Введи время как <b>ЧЧ:ММ</b>, например: <code>04:30</code>")
        return
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        await message.answer("Недопустимое время. Часы: 0-23, минуты: 0-59.")
        return

    cron_expr = f"{minute} {hour} * * *"
    data = await state.get_data()
    task_type = data.get("task_type")
    extra_data = data.get("extra_data")

    task_id = await add_task(task_type, cron_expr, extra_data)
    logger.info(f"Task {task_id} created by {message.from_user.id}: {task_type} {cron_expr}")

    label = _task_types.get(task_type, task_type)
    extra_info = f"\nКоманда: <code>{extra_data}</code>" if extra_data else ""

    await state.clear()
    await message.answer(
        success_text(
            f"Задача создана!\n\n"
            f"Тип: {label}\n"
            f"Расписание: ежедневно в {hour:02d}:{minute:02d}\n"
            f"Cron: <code>{cron_expr}</code>{extra_info}"
        )
    )
    await message.answer(SCHEDULER_MENU_TEXT, reply_markup=_scheduler_kb, parse_mode="HTML")


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
    schedule = _cron_to_human(cron_expr)
    extra_info = f"\nКоманда: <code>{extra_data}</code>" if extra_data else ""

    await state.clear()
    await message.answer(
        success_text(
            f"Задача создана!\n\n"
            f"Тип: {label}\n"
            f"Расписание: {schedule}\n"
            f"Cron: <code>{cron_expr}</code>{extra_info}"
        )
    )
    await message.answer(SCHEDULER_MENU_TEXT, reply_markup=_scheduler_kb, parse_mode="HTML")
