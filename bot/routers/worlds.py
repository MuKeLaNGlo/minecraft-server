from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from minecraft.backup_manager import backup_manager
from minecraft.world_manager import world_manager
from states.states import WorldState
from utils.formatting import section_header, success_text, error_text, format_bytes
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

worlds_router = Router()


async def _worlds_menu_text() -> str:
    current = await world_manager.get_current_world()
    return section_header(
        "🌍", "Миры",
        f"Управление мирами сервера.\nТекущий мир: <b>{current}</b>",
    )


async def _worlds_list_kb() -> InlineKeyboardMarkup:
    worlds = await world_manager.list_worlds()
    current = await world_manager.get_current_world()
    buttons = []

    for w in worlds:
        name = w["name"]
        generated = w.get("generated", True)
        label = f"🌍 {name}"
        if name == current:
            label += " (активный)"
        if not generated:
            label += " (новый)"
        else:
            label += f" — {w['size_mb']:.0f} МБ"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"world:detail:{name[:40]}")
        ])

    buttons.append([InlineKeyboardButton(text="➕ Создать мир", callback_data="world:create")])
    buttons.append(back_row("main"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@worlds_router.callback_query(F.data == "nav:worlds")
async def worlds_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    text = await _worlds_menu_text()
    kb = await _worlds_list_kb()
    await show_menu(callback, text, kb)
    await callback.answer()


@worlds_router.callback_query(F.data.startswith("world:"))
async def worlds_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "detail":
        name = ":".join(parts[2:])
        await callback.answer()
        current = await world_manager.get_current_world()
        worlds = await world_manager.list_worlds()
        world_info = next((w for w in worlds if w["name"] == name), None)

        if not world_info:
            text = error_text(f"Мир '{name}' не найден.")
            kb = await _worlds_list_kb()
            await show_menu(callback, text, kb)
            return

        generated = world_info.get("generated", True)
        is_active = name == current

        text = f"🌍 <b>{name}</b>"
        if is_active:
            text += " (активный)"
        if not generated:
            text += "\n\n⏳ Мир создан, но ещё не сгенерирован.\nПереключись и запусти сервер."
        else:
            size = f"{world_info['size_mb']:.0f} МБ"
            modified = world_info["last_modified"].strftime("%d.%m.%Y %H:%M")
            text += f"\n\nРазмер: {size}\nИзменён: {modified}"

        buttons = []
        if not is_active:
            buttons.append([InlineKeyboardButton(
                text="🔄 Переключиться", callback_data=f"world:switch:{name}"
            )])
        buttons.append([InlineKeyboardButton(
            text="✏ Переименовать", callback_data=f"world:rename:{name}"
        )])
        buttons.append([InlineKeyboardButton(
            text="💾 Бэкап этого мира", callback_data=f"world:backup:{name}"
        )])
        if not is_active:
            buttons.append([InlineKeyboardButton(
                text="🗑 Удалить", callback_data=f"world:del_confirm:{name}"
            )])
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="world:list")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, text, kb)

    elif action == "list":
        await callback.answer()
        text = await _worlds_menu_text()
        kb = await _worlds_list_kb()
        await show_menu(callback, text, kb)

    elif action == "switch":
        name = ":".join(parts[2:])
        await callback.answer()
        result = await world_manager.switch_world(name)
        if result["success"]:
            text = success_text(f"Мир переключён на '{name}'.\nПерезапусти сервер для применения.")
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Перезапустить сервер", callback_data="world:restart")],
                [InlineKeyboardButton(text="◀ К мирам", callback_data="world:list")],
            ])
        else:
            text = error_text(result["error"])
            kb = await _worlds_list_kb()
        await show_menu(callback, text, kb)

    elif action == "restart":
        from minecraft.docker_manager import docker_manager
        from minecraft.rcon import rcon
        import asyncio
        await callback.answer("Перезапускаю...")
        await callback.message.edit_text("⏳ Перезапуск сервера...")
        if await docker_manager.is_running():
            try:
                await rcon.execute("say Сервер перезапускается через 5 секунд!")
                await asyncio.sleep(5)
            except Exception:
                pass
        result = await docker_manager.restart()
        text = success_text(f"Сервер перезапущен.\nНовый мир загружается.")
        kb = await _worlds_list_kb()
        await show_menu(callback, text, kb)

    elif action == "del_confirm":
        name = ":".join(parts[2:])
        await callback.answer()
        text = f"Удалить мир <b>{name}</b>?\n\n⚠ Это действие необратимо!"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"world:delete:{name}"),
                InlineKeyboardButton(text="◀ Отмена", callback_data="world:list"),
            ],
        ])
        await show_menu(callback, text, kb)

    elif action == "delete":
        name = ":".join(parts[2:])
        await callback.answer("Удаляю...")
        result = await world_manager.delete_world(name)
        if result["success"]:
            text = success_text(result["message"])
        else:
            text = error_text(result["error"])
        kb = await _worlds_list_kb()
        await show_menu(callback, text, kb)

    elif action == "backup":
        name = ":".join(parts[2:])
        await callback.answer("Создаю бэкап...")
        await callback.message.edit_text(f"⏳ Создаю бэкап мира '{name}'...")
        result = await backup_manager.create_backup(world_name=name)
        if result["success"]:
            text = success_text(
                f"Бэкап мира '{name}' создан!\n"
                f"Файл: <code>{result['filename']}</code>\n"
                f"Размер: {format_bytes(result['size'])}"
            )
        else:
            text = error_text(result["error"])
        kb = await _worlds_list_kb()
        await show_menu(callback, text, kb)

    elif action == "rename":
        name = ":".join(parts[2:])
        await callback.answer()
        await state.update_data(renaming_world=name)
        await state.set_state(WorldState.waiting_new_name)
        await callback.message.answer(
            f"Текущее имя: <b>{name}</b>\n\nВведи новое имя мира:",
            reply_markup=CANCEL_REPLY_KB,
        )

    elif action == "create":
        await callback.answer()
        await state.set_state(WorldState.waiting_world_name)
        await callback.message.answer(
            "Введи название нового мира:",
            reply_markup=CANCEL_REPLY_KB,
        )


@worlds_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(WorldState.waiting_world_name, WorldState.waiting_new_name),
)
async def cancel_worlds(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@worlds_router.message(StateFilter(WorldState.waiting_world_name))
async def process_world_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Введи название мира:")
        return

    await state.clear()
    result = await world_manager.create_world(name)
    if result["success"]:
        text = success_text(result["message"])
    else:
        text = error_text(result["error"])
    await message.answer(text)

    menu_text = await _worlds_menu_text()
    kb = await _worlds_list_kb()
    await message.answer(menu_text, reply_markup=kb, parse_mode="HTML")


@worlds_router.message(StateFilter(WorldState.waiting_new_name))
async def process_rename(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Введи новое имя:")
        return

    data = await state.get_data()
    old_name = data.get("renaming_world", "")
    await state.clear()

    result = await world_manager.rename_world(old_name, new_name)
    if result["success"]:
        text = success_text(result["message"])
    else:
        text = error_text(result["error"])
    await message.answer(text)

    menu_text = await _worlds_menu_text()
    kb = await _worlds_list_kb()
    await message.answer(menu_text, reply_markup=kb, parse_mode="HTML")
