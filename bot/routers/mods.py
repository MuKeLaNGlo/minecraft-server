from datetime import datetime

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from core.config import config
from db.database import db
from minecraft.mod_manager import mod_manager
from services.modrinth import modrinth
from states.states import ModState
from utils.formatting import truncate, section_header, success_text, error_text, LINE
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

mods_router = Router()

MODS_MENU_TEXT = section_header(
    "📦", "Моды",
    f"Поиск, установка и обновление модов с Modrinth.\n"
    f"Лоадер: <b>{config.mc_loader}</b> | Версия: <b>{config.mc_version}</b>",
)

_mods_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск модов", callback_data="mod:search")],
        [InlineKeyboardButton(text="📋 Установленные", callback_data="mod:installed")],
        [InlineKeyboardButton(text="🔄 Проверить обновления", callback_data="mod:updates")],
        back_row("main"),
    ]
)


def _format_date(iso_str: str) -> str:
    """Format ISO date string to readable format."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except (ValueError, AttributeError):
        return "—"


@mods_router.callback_query(F.data == "nav:mods")
async def mods_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await show_menu(callback, MODS_MENU_TEXT, _mods_kb)
    await callback.answer()


@mods_router.callback_query(F.data.startswith("mod:"))
async def mods_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "search":
        await callback.answer()
        await state.set_state(ModState.waiting_search_query)
        await callback.message.answer(
            "Введи название мода для поиска:", reply_markup=CANCEL_REPLY_KB
        )

    elif action == "installed":
        await callback.answer()
        mods = await mod_manager.list_installed()
        if not mods:
            await show_menu(callback, "Установленных модов нет.", _mods_kb)
            return

        buttons = []
        for mod in mods:
            slug, name = mod[1], mod[2]
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑 {name}", callback_data=f"mod:remove:{slug}"
                )
            ])
        buttons.append(back_row("mods"))
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, f"📋 Установленные моды ({len(mods)}):", kb)

    elif action == "updates":
        await callback.answer("Проверяю обновления...")
        await callback.message.edit_text("⏳ Проверяю обновления...")
        updates = await mod_manager.check_updates()
        if not updates:
            text = success_text("Все моды актуальны!")
        else:
            lines = ["Доступные обновления:\n"]
            for u in updates:
                lines.append(f"  - {u['name']}: версия {u['new_version']}")
            text = "\n".join(lines)
        await show_menu(callback, text, _mods_kb)

    elif action == "results":
        offset = int(parts[2]) if len(parts) > 2 else 0
        await callback.answer()
        data = await state.get_data()
        query = data.get("search_query", "")
        if not query:
            await show_menu(callback, "Поиск устарел, попробуй заново.", _mods_kb)
            return
        await _show_search_results(callback.message, state, query, offset, edit=True)

    elif action == "detail":
        slug = parts[2]
        await callback.answer()
        # Remember current search offset so "back" returns to correct page
        data = await state.get_data()
        search_offset = data.get("search_offset", 0)
        try:
            project = await modrinth.get_project(slug)
            versions = await modrinth.get_versions(slug)
            latest = versions[0]["version_number"] if versions else "нет"

            title = project.get("title", slug)
            desc = truncate(project.get("description", ""), 500)
            downloads = project.get("downloads", 0)
            updated = _format_date(project.get("updated", ""))
            categories = ", ".join(project.get("categories", [])) or "—"
            license_info = project.get("license", {})
            license_id = license_info.get("id", "—") if isinstance(license_info, dict) else str(license_info) if license_info else "—"
            source_url = project.get("source_url", "")

            text = (
                f"{LINE}\n"
                f"📦 <b>{title}</b>\n"
                f"{LINE}\n\n"
                f"{desc}\n\n"
                f"📊 Загрузки: {downloads:,}\n"
                f"📅 Обновлён: {updated}\n"
                f"🏷 Категории: {categories}\n"
                f"📜 Лицензия: {license_id}\n"
            )
            if source_url:
                text += f"🔗 Исходный код: {source_url}\n"
            text += (
                f"\n📥 Последняя версия: <b>{latest}</b>\n"
                f"🔧 Лоадер: {config.mc_loader} | MC: {config.mc_version}"
            )

            installed = await db.mod_installed(slug)
            buttons = []
            if installed:
                mod_data = await db.get_mod_by_slug(slug)
                if mod_data:
                    inst_file = mod_data[4] if len(mod_data) > 4 else ""
                    if inst_file:
                        text += f"\n\n✅ Установлен: <code>{inst_file}</code>"
                buttons.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"mod:remove:{slug}")])
            else:
                # Show required dependencies before install
                if versions:
                    try:
                        req_deps = await mod_manager._resolve_dependencies(versions[0])
                        if req_deps:
                            dep_names = ", ".join(d["name"] for d in req_deps)
                            text += f"\n\n📎 Зависимости: {dep_names}"
                    except Exception:
                        pass
                buttons.append([InlineKeyboardButton(text="📥 Установить", callback_data=f"mod:install:{slug}")])
            buttons.append([InlineKeyboardButton(
                text="🔗 Modrinth", url=f"https://modrinth.com/mod/{slug}"
            )])
            # If we came from search, go back to results; otherwise go to mods menu
            if data.get("search_query"):
                buttons.append([InlineKeyboardButton(
                    text="◀ К результатам", callback_data=f"mod:results:{search_offset}"
                )])
            else:
                buttons.append(back_row("mods"))
            detail_kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await show_menu(callback, text, detail_kb)
        except Exception as e:
            await show_menu(callback, error_text(f"Ошибка загрузки: {e}"), _mods_kb)

    elif action == "install":
        slug = parts[2]
        await callback.answer("Устанавливаю...")
        await callback.message.edit_text("⏳ Скачиваю и устанавливаю мод...")
        result = await mod_manager.install_mod(slug)
        if result["success"]:
            lines = [
                f"Мод установлен!\n"
                f"Название: {result['name']}\n"
                f"Версия: {result['version']}\n"
                f"Файл: <code>{result['filename']}</code>"
            ]
            deps = result.get("deps", [])
            if deps:
                lines.append(f"\n📎 Зависимости ({len(deps)}):")
                for d in deps:
                    lines.append(f"  + {d['name']} {d['version']}")
            lines.append("\nПерезапусти сервер для применения.")
            text = success_text("\n".join(lines))
        else:
            text = error_text(result["error"])
        await show_menu(callback, text, _mods_kb)

    elif action == "remove":
        slug = parts[2]
        await callback.answer("Удаляю...")
        result = await mod_manager.remove_mod(slug)
        if result["success"]:
            text = success_text(f"Мод {result['name']} удалён. Перезапусти сервер.")
        else:
            text = error_text(result["error"])
        await show_menu(callback, text, _mods_kb)

    elif action in ("back", "mods"):
        await callback.answer()
        await show_menu(callback, MODS_MENU_TEXT, _mods_kb)


async def _show_search_results(
    message, state: FSMContext, query: str, offset: int = 0, edit: bool = False
):
    # Save query + offset in state so detail/pagination callbacks can return here
    await state.update_data(search_query=query, search_offset=offset)

    try:
        data = await modrinth.search(query, limit=5, offset=offset)
    except Exception as e:
        text = error_text(f"Ошибка поиска: {e}")
        if edit:
            await message.edit_text(text, reply_markup=_mods_kb)
        else:
            await message.answer(text, reply_markup=_mods_kb)
        return

    hits = data.get("hits", [])
    total = data.get("total_hits", 0)

    if not hits:
        text = "Ничего не найдено."
        if edit:
            await message.edit_text(text, reply_markup=_mods_kb)
        else:
            await message.answer(text, reply_markup=_mods_kb)
        await state.clear()
        return

    lines = [f"🔍 <b>Результаты</b> ({offset + 1}–{min(offset + 5, total)} из {total})\n"]
    buttons = []
    for hit in hits:
        slug = hit.get("slug", hit.get("project_id", "?"))
        title = hit.get("title", slug)
        downloads = hit.get("downloads", 0)
        desc = truncate(hit.get("description", ""), 100)
        cats = ", ".join(hit.get("categories", [])[:3])

        lines.append(f"<b>{title}</b>")
        if desc:
            lines.append(f"  {desc}")
        lines.append("")

        dl_short = f"{downloads // 1000}K" if downloads >= 1000 else str(downloads)
        cats_short = f" · {cats}" if cats else ""
        btn_label = f"{title} — {dl_short} DL{cats_short}"
        buttons.append([
            InlineKeyboardButton(
                text=btn_label,
                callback_data=f"mod:detail:{slug[:50]}",
            ),
        ])

    nav_buttons = []
    if offset > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀ Назад", callback_data=f"mod:results:{offset - 5}")
        )
    if offset + 5 < total:
        nav_buttons.append(
            InlineKeyboardButton(text="Далее ▶", callback_data=f"mod:results:{offset + 5}")
        )
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="✖ Закрыть", callback_data="mod:back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "\n".join(lines)

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@mods_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(ModState.waiting_search_query),
)
async def cancel_mods(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@mods_router.message(StateFilter(ModState.waiting_search_query))
async def search_query_handler(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("Введи название мода:")
        return
    await state.clear()
    await _show_search_results(message, state, query)
