from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from db.database import db
from minecraft.backup_manager import backup_manager
from states.states import BackupState
from utils.formatting import format_bytes, section_header, success_text, error_text
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row

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
        await callback.message.edit_text(text, reply_markup=_backups_kb)

    elif action == "list":
        await callback.answer()
        backups = await backup_manager.list_backups()
        if not backups:
            await show_menu(callback, "Бэкапов нет.", _backups_kb)
            return

        buttons = []
        for bak in backups[:20]:
            bak_id, filename, size, world, created = bak
            size_str = format_bytes(size) if size else "?"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{filename} ({size_str})",
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
        filename = row[1]
        detail_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📥 Скачать", callback_data=f"bak:download:{bak_id}")],
                [InlineKeyboardButton(text="♻ Восстановить", callback_data=f"bak:restore:{bak_id}")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="bak:list")],
            ]
        )
        size_str = format_bytes(row[2]) if row[2] else "?"
        await show_menu(
            callback,
            f"Бэкап: <code>{filename}</code>\n"
            f"Размер: {size_str}\nМир: {row[3]}\nДата: {row[4][:19] if row[4] else '?'}",
            detail_kb,
        )

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
            await callback.message.answer(error_text("Файл не найден на диске."))

    elif action == "restore":
        bak_id = int(parts[2])
        row = await db.get_backup_by_id(bak_id)
        if not row:
            await callback.answer("Бэкап не найден")
            return
        filename = row[1]
        await callback.answer()
        await state.update_data(restore_filename=filename)
        await state.set_state(BackupState.confirm_restore)
        confirm_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, восстановить", callback_data="bak:confirm_restore"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="bak:cancel_restore"),
                ],
            ]
        )
        await show_menu(
            callback,
            f"Восстановить бэкап <code>{filename}</code>?\n\n"
            f"⚠ Сервер должен быть остановлен! Текущий мир будет перезаписан.",
            confirm_kb,
        )

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

        result = await backup_manager.restore_backup(filename)
        if result["success"]:
            logger.info(f"Backup restored [{callback.from_user.id}]: {filename}")
            text = success_text(f"Бэкап восстановлен! Мир: {result['world_name']}.\nЗапусти сервер.")
        else:
            text = error_text(result["error"])
        await show_menu(callback, text, _backups_kb)
        await state.clear()

    elif action == "cancel_restore":
        await callback.answer()
        await show_menu(callback, "Восстановление отменено.", _backups_kb)
        await state.clear()

    elif action == "rotate":
        await callback.answer("Ротация...")
        removed = await backup_manager.rotate_backups(keep=10)
        logger.info(f"Backup rotation [{callback.from_user.id}]: removed {removed}")
        text = f"Удалено старых бэкапов: {removed}" if removed else "Нечего удалять."
        await show_menu(callback, text, _backups_kb)

    elif action == "backups":
        # "back to backups" alias
        await callback.answer()
        await show_menu(callback, BACKUPS_MENU_TEXT, _backups_kb)
