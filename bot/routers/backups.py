from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from db.database import db
from minecraft.backup_manager import backup_manager
from minecraft.world_manager import world_manager
from states.states import BackupState
from utils.formatting import format_bytes, section_header, success_text, error_text
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, restart_row, return_to_menu, CANCEL_REPLY_KB

backups_router = Router()

BACKUPS_MENU_TEXT = section_header(
    "💾", "Бэкапы",
    "Создание, восстановление и ротация бэкапов мира.",
)

_backups_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💾 Создать бэкап", callback_data="bak:create")],
        [InlineKeyboardButton(text="📋 Список бэкапов", callback_data="bak:list")],
        [InlineKeyboardButton(text="🔄 Ротация (оставить 10)", callback_data="bak:rotate")],
        back_row("main"),
    ]
)


@backups_router.callback_query(F.data == "nav:backups")
async def backups_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await show_menu(callback, BACKUPS_MENU_TEXT, _backups_kb)
    await callback.answer()


@backups_router.callback_query(F.data.startswith("bak:"))
async def backups_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "create":
        await callback.answer("Создаю бэкап...")
        await callback.message.edit_text("⏳ Создаю бэкап, подожди...")
        result = await backup_manager.create_backup()
        if result["success"]:
            logger.info(f"Backup created [{callback.from_user.id}]: {result['filename']}")
            text = success_text(
                f"Бэкап создан!\n"
                f"Файл: <code>{result['filename']}</code>\n"
                f"Размер: {format_bytes(result['size'])}"
            )
        else:
            text = error_text(result["error"])
        await callback.message.edit_text(text, reply_markup=_backups_kb, parse_mode="HTML")

    elif action == "list":
        await callback.answer()
        backups = await backup_manager.list_backups()
        if not backups:
            await show_menu(callback, "Бэкапов нет.", _backups_kb)
            return

        buttons = []
        for bak in backups[:20]:
            bak_id, filename, size, bak_world, created = bak
            size_str = format_bytes(size) if size else "?"
            # Shorter label: world + date + size
            short = f"🌍 {bak_world} | {created[:16] if created else '?'} ({size_str})"
            buttons.append([
                InlineKeyboardButton(
                    text=short,
                    callback_data=f"bak:detail:{bak_id}",
                )
            ])
        buttons.append(back_row("backups"))
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, "📋 Список бэкапов:", kb)

    elif action == "detail":
        bak_id = int(parts[2])
        await callback.answer()
        row = await db.get_backup_by_id(bak_id)
        if not row:
            await show_menu(callback, error_text("Бэкап не найден в БД."), _backups_kb)
            return

        _, filename, size, bak_world, created = row
        current_world = await world_manager.get_current_world()
        size_str = format_bytes(size) if size else "?"
        date_str = created[:19] if created else "?"

        text = (
            f"💾 <b>Бэкап</b>\n\n"
            f"Файл: <code>{filename}</code>\n"
            f"Размер: {size_str}\n"
            f"Мир бэкапа: <b>{bak_world}</b>\n"
            f"Дата: {date_str}\n\n"
            f"Текущий активный мир: <b>{current_world}</b>"
        )

        detail_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📥 Скачать", callback_data=f"bak:download:{bak_id}")],
                [InlineKeyboardButton(text="♻ Восстановить", callback_data=f"bak:restore:{bak_id}")],
                [InlineKeyboardButton(text="📋 Восстановить как копию", callback_data=f"bak:clone:{bak_id}")],
                [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"bak:del_confirm:{bak_id}")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="bak:list")],
            ]
        )
        await show_menu(callback, text, detail_kb)

    elif action == "download":
        bak_id = int(parts[2])
        row = await db.get_backup_by_id(bak_id)
        if not row:
            await callback.answer("Бэкап не найден")
            return
        filename = row[1]
        await callback.answer("Отправляю файл...")
        path = backup_manager.get_backup_path(filename)
        if path and path.stat().st_size < 50 * 1024 * 1024:
            doc = FSInputFile(path)
            await callback.message.answer_document(doc)
        elif path:
            await callback.message.answer(
                f"Файл слишком большой для Telegram ({format_bytes(path.stat().st_size)}). "
                f"Скачай вручную из папки backups/."
            )
        else:
            await callback.message.answer(error_text("Файл не найден на диске."), parse_mode="HTML")

    elif action == "restore":
        bak_id = int(parts[2])
        row = await db.get_backup_by_id(bak_id)
        if not row:
            await callback.answer("Бэкап не найден")
            return

        _, filename, _, bak_world, _ = row
        current_world = await world_manager.get_current_world()
        await callback.answer()
        await state.update_data(restore_filename=filename, restore_world=bak_world)
        await state.set_state(BackupState.confirm_restore)

        # Build warning message
        if bak_world == current_world:
            warning = (
                f"♻ <b>Восстановление бэкапа</b>\n\n"
                f"Файл: <code>{filename}</code>\n"
                f"Мир бэкапа: <b>{bak_world}</b>\n\n"
                f"Бэкап будет восстановлен в мир <b>{bak_world}</b> "
                f"(это текущий активный мир).\n"
                f"Все данные мира <b>{bak_world}</b> будут перезаписаны.\n\n"
                f"⚠ Сервер должен быть остановлен!"
            )
        else:
            warning = (
                f"♻ <b>Восстановление бэкапа</b>\n\n"
                f"Файл: <code>{filename}</code>\n"
                f"Мир бэкапа: <b>{bak_world}</b>\n"
                f"Текущий активный мир: <b>{current_world}</b>\n\n"
                f"⚠ <b>Внимание!</b> Бэкап восстановится в мир <b>{bak_world}</b>, "
                f"а не в текущий мир ({current_world}). "
                f"Данные мира <b>{bak_world}</b> будут перезаписаны.\n\n"
                f"⚠ Сервер должен быть остановлен!"
            )

        confirm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, восстановить", callback_data="bak:confirm_restore"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="bak:cancel_restore"),
                ],
            ]
        )
        await show_menu(callback, warning, confirm_kb)

    elif action == "confirm_restore":
        await callback.answer("Восстанавливаю...")
        data = await state.get_data()
        filename = data.get("restore_filename")
        if not filename:
            await show_menu(callback, error_text("Файл не указан."), _backups_kb)
            await state.clear()
            return

        from minecraft.docker_manager import docker_manager
        if await docker_manager.is_running():
            await show_menu(
                callback,
                "⚠ Сервер ещё запущен! Сначала останови сервер.",
                _backups_kb,
            )
            await state.clear()
            return

        await callback.message.edit_text("⏳ Восстанавливаю бэкап...")
        result = await backup_manager.restore_backup(filename)
        if result["success"]:
            logger.info(f"Backup restored [{callback.from_user.id}]: {filename}")
            text = success_text(f"Бэкап восстановлен!\nМир: <b>{result['world_name']}</b>.\nЗапусти сервер.")
        else:
            text = error_text(result["error"])
        kb = InlineKeyboardMarkup(inline_keyboard=_backups_kb.inline_keyboard.copy())
        if result["success"]:
            kb.inline_keyboard.insert(0, restart_row())
        await show_menu(callback, text, kb)
        await state.clear()

    elif action == "cancel_restore":
        await callback.answer()
        await show_menu(callback, "Восстановление отменено.", _backups_kb)
        await state.clear()

    elif action == "clone":
        # Restore backup as a copy (new world name)
        bak_id = int(parts[2])
        row = await db.get_backup_by_id(bak_id)
        if not row:
            await callback.answer("Бэкап не найден")
            return

        _, filename, _, bak_world, _ = row
        await callback.answer()
        await state.update_data(clone_filename=filename, clone_source_world=bak_world)
        await state.set_state(BackupState.waiting_clone_name)
        await callback.message.answer(
            f"📋 <b>Восстановить как копию</b>\n\n"
            f"Бэкап мира: <b>{bak_world}</b>\n"
            f"Бэкап будет распакован в новую папку мира.\n\n"
            f"Введи имя для нового мира:",
            reply_markup=CANCEL_REPLY_KB,
            parse_mode="HTML",
        )

    elif action == "del_confirm":
        bak_id = int(parts[2])
        row = await db.get_backup_by_id(bak_id)
        if not row:
            await callback.answer("Бэкап не найден")
            return
        _, filename, size, bak_world, created = row
        await callback.answer()
        size_str = format_bytes(size) if size else "?"
        confirm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"bak:delete:{bak_id}"),
                    InlineKeyboardButton(text="◀ Отмена", callback_data=f"bak:detail:{bak_id}"),
                ],
            ]
        )
        await show_menu(
            callback,
            f"Удалить бэкап?\n\n"
            f"Файл: <code>{filename}</code>\n"
            f"Мир: {bak_world} | Размер: {size_str}\n\n"
            f"⚠ Это действие необратимо!",
            confirm_kb,
        )

    elif action == "delete":
        bak_id = int(parts[2])
        row = await db.get_backup_by_id(bak_id)
        if not row:
            await callback.answer("Бэкап не найден")
            return
        filename = row[1]
        await callback.answer("Удаляю...")
        result = await backup_manager.delete_backup(filename)
        if result["success"]:
            logger.info(f"Backup deleted [{callback.from_user.id}]: {filename}")
            text = success_text(f"Бэкап <code>{filename}</code> удалён.")
        else:
            text = error_text(result.get("error", "Ошибка удаления."))
        await show_menu(callback, text, _backups_kb)

    elif action == "rotate":
        await callback.answer()
        confirm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, очистить", callback_data="bak:confirm_rotate"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="bak:backups"),
                ],
            ]
        )
        await show_menu(
            callback,
            "Удалить старые бэкапы?\n\nОстанутся только последние 10.",
            confirm_kb,
        )

    elif action == "confirm_rotate":
        await callback.answer("Ротация...")
        removed = await backup_manager.rotate_backups(keep=10)
        logger.info(f"Backup rotation [{callback.from_user.id}]: removed {removed}")
        text = f"Удалено старых бэкапов: {removed}" if removed else "Нечего удалять."
        await show_menu(callback, text, _backups_kb)

    elif action == "backups":
        # "back to backups" alias
        await callback.answer()
        await show_menu(callback, BACKUPS_MENU_TEXT, _backups_kb)


# --- FSM: clone name input ---

@backups_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(BackupState.waiting_clone_name),
)
async def cancel_clone(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@backups_router.message(StateFilter(BackupState.waiting_clone_name))
async def process_clone_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Введи имя нового мира:")
        return

    if "/" in name or "\\" in name or ".." in name:
        await message.answer("Недопустимое имя. Попробуй другое:")
        return

    data = await state.get_data()
    filename = data.get("clone_filename")
    if not filename:
        await state.clear()
        await message.answer(error_text("Ошибка: бэкап не выбран."), parse_mode="HTML")
        await return_to_menu(message)
        return

    from minecraft.docker_manager import docker_manager
    if await docker_manager.is_running():
        # Server can be running for clone — it goes to a new dir
        pass

    await state.clear()
    status_msg = await message.answer("⏳ Распаковываю бэкап...")
    result = await backup_manager.restore_as_copy(filename, name)
    if result["success"]:
        logger.info(f"Backup cloned [{message.from_user.id}]: {filename} -> {name}")
        text = success_text(
            f"Бэкап восстановлен как копия!\n"
            f"Новый мир: <b>{result['world_name']}</b>\n\n"
            f"Переключись на него в разделе «Миры», если нужно."
        )
    else:
        text = error_text(result["error"])
    await status_msg.edit_text(text, parse_mode="HTML")
    await return_to_menu(message)
