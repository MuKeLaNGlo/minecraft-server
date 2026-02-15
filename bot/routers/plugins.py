import os
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path

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

from core.config import config
from db.database import db
from minecraft.plugin_manager import plugin_manager, _plugin_loaders
from services.modrinth import modrinth
from states.states import PluginState
from utils.formatting import truncate, section_header, success_text, error_text, LINE
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, restart_row, return_to_menu, CANCEL_REPLY_KB, MENU_REPLY_KB

plugins_router = Router()


async def _plugins_menu_text() -> str:
    count = len(await plugin_manager.list_installed())
    return section_header(
        "🔌", "Плагины",
        f"Установлено плагинов: <b>{count}</b>\n"
        f"Сервер: <b>{config.mc_loader}</b> | Версия: <b>{config.mc_version}</b>",
    )


_plugins_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск плагинов", callback_data="plug:search")],
        [InlineKeyboardButton(text="📋 Установленные", callback_data="plug:installed")],
        [
            InlineKeyboardButton(text="📤 Загрузить плагин", callback_data="plug:upload"),
            InlineKeyboardButton(text="🔃 Синхронизация", callback_data="plug:sync"),
        ],
        [InlineKeyboardButton(text="🔄 Проверить обновления", callback_data="plug:updates")],
        back_row("main"),
    ]
)


def _format_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except (ValueError, AttributeError):
        return "—"


@plugins_router.callback_query(F.data == "nav:plugins")
async def plugins_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await plugin_manager.sync_plugins_dir()
    await show_menu(callback, await _plugins_menu_text(), _plugins_kb)
    await callback.answer()


@plugins_router.callback_query(F.data.startswith("plug:"))
async def plugins_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "search":
        await callback.answer()
        await state.set_state(PluginState.waiting_search_query)
        await callback.message.answer(
            "Введи название плагина для поиска:", reply_markup=CANCEL_REPLY_KB
        )

    elif action == "installed":
        await callback.answer()
        await plugin_manager.sync_plugins_dir()
        plugins = await plugin_manager.list_installed()
        if not plugins:
            await show_menu(callback, "Установленных плагинов нет.", _plugins_kb)
            return

        buttons = []
        for p in plugins:
            slug, name = p[1], p[2]
            buttons.append([
                InlineKeyboardButton(
                    text=f"🗑 {name}", callback_data=f"plug:remove:{slug}"
                )
            ])
        buttons.append([
            InlineKeyboardButton(text="📥 Скачать все .jar", callback_data="plug:download:files"),
            InlineKeyboardButton(text="📦 Скачать .zip", callback_data="plug:download:zip"),
        ])
        buttons.append(back_row("plugins"))
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, f"📋 Установленные плагины ({len(plugins)}):", kb)

    elif action == "updates":
        await callback.answer("Проверяю обновления...")
        await callback.message.edit_text("⏳ Проверяю обновления...")
        updates = await plugin_manager.check_updates()
        if not updates:
            text = success_text("Все плагины актуальны!")
        else:
            lines = ["Доступные обновления:\n"]
            for u in updates:
                lines.append(f"  - {u['name']}: версия {u['new_version']}")
            text = "\n".join(lines)
        await show_menu(callback, text, _plugins_kb)

    elif action == "results":
        offset = int(parts[2]) if len(parts) > 2 else 0
        await callback.answer()
        data = await state.get_data()
        query = data.get("search_query", "")
        if not query:
            await show_menu(callback, "Поиск устарел, попробуй заново.", _plugins_kb)
            return
        server_only = data.get("server_only", False)
        await _show_search_results(callback.message, state, query, offset, edit=True, server_only=server_only)

    elif action == "toggle_filter":
        await callback.answer()
        data = await state.get_data()
        query = data.get("search_query", "")
        if not query:
            await show_menu(callback, "Поиск устарел, попробуй заново.", _plugins_kb)
            return
        server_only = not data.get("server_only", False)
        await _show_search_results(callback.message, state, query, 0, edit=True, server_only=server_only)

    elif action == "detail":
        slug = parts[2]
        await callback.answer()
        data = await state.get_data()
        search_offset = data.get("search_offset", 0)
        try:
            project = await modrinth.get_project(slug)
            versions = await modrinth.get_versions(slug, loaders=_plugin_loaders())
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
                f"🔌 <b>{title}</b>\n"
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
                f"🔧 Сервер: {config.mc_loader} | MC: {config.mc_version}"
            )

            installed = await db.plugin_installed(slug)
            buttons = []
            if installed:
                plugin_data = await db.get_plugin_by_slug(slug)
                if plugin_data:
                    inst_file = plugin_data[4] if len(plugin_data) > 4 else ""
                    if inst_file:
                        text += f"\n\n✅ Установлен: <code>{inst_file}</code>"
                buttons.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"plug:remove:{slug}")])
            else:
                if versions:
                    try:
                        req_deps = await plugin_manager._resolve_dependencies(versions[0])
                        if req_deps:
                            dep_names = ", ".join(d["name"] for d in req_deps)
                            text += f"\n\n📎 Зависимости: {dep_names}"
                    except Exception:
                        pass
                buttons.append([InlineKeyboardButton(text="📥 Установить", callback_data=f"plug:install:{slug}")])
            buttons.append([InlineKeyboardButton(
                text="🔗 Modrinth", url=f"https://modrinth.com/plugin/{slug}"
            )])
            if data.get("search_query"):
                buttons.append([InlineKeyboardButton(
                    text="◀ К результатам", callback_data=f"plug:results:{search_offset}"
                )])
            else:
                buttons.append(back_row("plugins"))
            detail_kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await show_menu(callback, text, detail_kb)
        except Exception as e:
            await show_menu(callback, error_text(f"Ошибка загрузки: {e}"), _plugins_kb)

    elif action == "install":
        slug = parts[2]
        await callback.answer("Устанавливаю...")
        await callback.message.edit_text("⏳ Скачиваю и устанавливаю плагин...")
        result = await plugin_manager.install_plugin(slug)
        if result["success"]:
            lines = [
                f"Плагин установлен!\n"
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
        kb = InlineKeyboardMarkup(inline_keyboard=_plugins_kb.inline_keyboard.copy())
        if result["success"]:
            kb.inline_keyboard.insert(0, restart_row())
        await show_menu(callback, text, kb)

    elif action == "remove":
        slug = parts[2]
        await callback.answer()
        plugin = await db.get_plugin_by_slug(slug)
        name = plugin[2] if plugin else slug
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"plug:confirm_remove:{slug}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="plug:installed"),
            ],
        ])
        await show_menu(callback, f"Удалить плагин <b>{name}</b>?", confirm_kb)

    elif action == "confirm_remove":
        slug = parts[2]
        await callback.answer("Удаляю...")
        result = await plugin_manager.remove_plugin(slug)
        if result["success"]:
            text = success_text(f"Плагин {result['name']} удалён. Перезапусти сервер.")
        else:
            text = error_text(result["error"])
        kb = InlineKeyboardMarkup(inline_keyboard=_plugins_kb.inline_keyboard.copy())
        if result["success"]:
            kb.inline_keyboard.insert(0, restart_row())
        await show_menu(callback, text, kb)

    elif action == "download":
        mode = parts[2]  # "files" or "zip"
        await callback.answer("Готовлю файлы...")
        plugins_dir = plugin_manager.plugins_dir
        jars = sorted(plugins_dir.glob("*.jar"))
        if not jars:
            await show_menu(callback, "Нет .jar файлов для скачивания.", _plugins_kb)
            return

        if mode == "zip":
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for jar in jars:
                        zf.write(jar, jar.name)
                doc = FSInputFile(tmp_path, filename="plugins.zip")
                await callback.message.answer_document(
                    doc, caption=f"📦 Все плагины ({len(jars)} шт.)",
                )
            except Exception as e:
                logger.error(f"Plugin zip download error: {e}")
                await callback.message.answer(f"❌ Ошибка: {e}")
            finally:
                os.unlink(tmp_path)
        else:
            for jar in jars:
                try:
                    doc = FSInputFile(jar)
                    await callback.message.answer_document(doc)
                except Exception as e:
                    logger.error(f"Plugin send error ({jar.name}): {e}")
                    await callback.message.answer(f"❌ {jar.name}: {e}")

    elif action == "sync":
        await callback.answer("Сканирую папку plugins...")
        await callback.message.edit_text("⏳ Синхронизация с папкой plugins...")
        result = await plugin_manager.sync_plugins_dir()
        added = result["added"]
        removed = result["removed"]
        if not added and not removed:
            text = success_text("Всё синхронизировано, новых плагинов не обнаружено.")
        else:
            lines = []
            if added:
                lines.append(f"Добавлено в БД ({len(added)}):")
                for f in added:
                    lines.append(f"  + {f}")
            if removed:
                lines.append(f"Удалено из БД ({len(removed)}):")
                for f in removed:
                    lines.append(f"  − {f}")
            text = success_text("\n".join(lines))
        await show_menu(callback, text, _plugins_kb)

    elif action == "upload":
        await callback.answer()
        await state.update_data(pending_uploads=[])
        await state.set_state(PluginState.waiting_plugin_files)
        await callback.message.answer(
            "📤 Отправь .jar файл плагина (можно несколько).\n\n"
            "После загрузки появится предпросмотр для подтверждения.",
            reply_markup=CANCEL_REPLY_KB,
            parse_mode="HTML",
        )

    elif action == "upload_confirm":
        await callback.answer("Устанавливаю...")
        data = await state.get_data()
        pending = data.get("pending_uploads", [])
        if not pending:
            await state.clear()
            await callback.message.edit_text("Нет файлов для установки.")
            await return_to_menu(callback.message)
            return

        await callback.message.edit_text("⏳ Устанавливаю плагины...")
        all_installed = []
        all_skipped = []
        all_errors = []
        for p in pending:
            result = await plugin_manager.install_pending(
                p["tmp_path"], p["original_name"], p["is_archive"],
            )
            all_installed.extend(result.get("installed", []))
            all_skipped.extend(result.get("skipped", []))
            all_errors.extend(result.get("errors", []))

        await state.clear()
        lines = []
        if all_installed:
            lines.append(f"✅ Установлено ({len(all_installed)}):")
            for f in all_installed:
                lines.append(f"  + {f}")
        if all_skipped:
            lines.append(f"\n⏭ Пропущено ({len(all_skipped)}):")
            for f in all_skipped:
                lines.append(f"  • {f}")
        if all_errors:
            lines.append(f"\n❌ Ошибки ({len(all_errors)}):")
            for e in all_errors:
                lines.append(f"  • {e}")
        if all_installed:
            lines.append("\nПерезапусти сервер для применения.")
        text = success_text("\n".join(lines)) if all_installed else error_text("\n".join(lines) or "Нечего устанавливать.")
        await callback.message.edit_text(text, parse_mode="HTML")
        menu_text = await _plugins_menu_text()
        kb = InlineKeyboardMarkup(inline_keyboard=_plugins_kb.inline_keyboard.copy())
        if all_installed:
            kb.inline_keyboard.insert(0, restart_row())
        await callback.message.answer(menu_text, reply_markup=kb, parse_mode="HTML")
        await callback.message.answer("Готово.", reply_markup=MENU_REPLY_KB)

    elif action == "upload_cancel":
        await callback.answer()
        data = await state.get_data()
        for p in data.get("pending_uploads", []):
            try:
                os.unlink(p.get("tmp_path", ""))
            except OSError:
                pass
        await state.clear()
        await callback.message.edit_text("Загрузка отменена.")
        await return_to_menu(callback.message)

    elif action in ("back", "plugins"):
        await callback.answer()
        await show_menu(callback, await _plugins_menu_text(), _plugins_kb)


async def _show_search_results(
    message, state: FSMContext, query: str, offset: int = 0,
    edit: bool = False, server_only: bool = False,
):
    await state.update_data(search_query=query, search_offset=offset, server_only=server_only)

    try:
        data = await modrinth.search(
            query, limit=5, offset=offset, server_only=server_only,
            project_type="plugin", loaders=_plugin_loaders(),
        )
    except Exception as e:
        text = error_text(f"Ошибка поиска: {e}")
        if edit:
            await message.edit_text(text, reply_markup=_plugins_kb)
        else:
            await message.answer(text, reply_markup=_plugins_kb)
        return

    hits = data.get("hits", [])
    total = data.get("total_hits", 0)

    if not hits:
        if server_only:
            text = "Серверных плагинов не найдено."
            toggle_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Показать все", callback_data="plug:toggle_filter")],
                [InlineKeyboardButton(text="✖ Закрыть", callback_data="plug:back")],
            ])
            if edit:
                await message.edit_text(text, reply_markup=toggle_kb)
            else:
                await message.answer(text, reply_markup=toggle_kb)
        else:
            text = "Ничего не найдено."
            if edit:
                await message.edit_text(text, reply_markup=_plugins_kb)
            else:
                await message.answer(text, reply_markup=_plugins_kb)
            await state.clear()
        return

    filter_label = "🖥 Серверные" if server_only else "📋 Все"
    lines = [f"🔍 <b>Результаты</b> ({offset + 1}–{min(offset + 5, total)} из {total}) · {filter_label}\n"]
    buttons = []
    for hit in hits:
        slug = hit.get("slug", hit.get("project_id", "?"))
        title = hit.get("title", slug)
        downloads = hit.get("downloads", 0)
        desc = truncate(hit.get("description", ""), 100)

        lines.append(f"<b>{title}</b>")
        if desc:
            lines.append(f"  {desc}")
        lines.append("")

        dl_short = f"{downloads // 1000}K" if downloads >= 1000 else str(downloads)
        btn_label = f"🔌 {title} — {dl_short} DL"
        buttons.append([
            InlineKeyboardButton(
                text=btn_label,
                callback_data=f"plug:detail:{slug[:50]}",
            ),
        ])

    nav_buttons = []
    if offset > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀ Назад", callback_data=f"plug:results:{offset - 5}")
        )
    if offset + 5 < total:
        nav_buttons.append(
            InlineKeyboardButton(text="Далее ▶", callback_data=f"plug:results:{offset + 5}")
        )
    if nav_buttons:
        buttons.append(nav_buttons)

    toggle_text = "📋 Показать все" if server_only else "🖥 Только серверные"
    buttons.append([InlineKeyboardButton(text=toggle_text, callback_data="plug:toggle_filter")])
    buttons.append([InlineKeyboardButton(text="✖ Закрыть", callback_data="plug:back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "\n".join(lines)

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@plugins_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(
        PluginState.waiting_search_query,
        PluginState.waiting_plugin_files,
        PluginState.waiting_upload_confirm,
    ),
)
async def cancel_plugins(message: Message, state: FSMContext):
    data = await state.get_data()
    for p in data.get("pending_uploads", []):
        try:
            os.unlink(p.get("tmp_path", ""))
        except OSError:
            pass
    await state.clear()
    await return_to_menu(message)


def _build_preview_text(pending: list) -> str:
    total_new = []
    total_existing = []
    for p in pending:
        total_new.extend(p["new"])
        total_existing.extend(p["existing"])

    lines = ["📋 <b>Предпросмотр загрузки</b>\n"]
    if total_new:
        lines.append(f"✅ Будет установлено ({len(total_new)}):")
        for n in total_new:
            lines.append(f"  + {n}")
    if total_existing:
        lines.append(f"\n⏭ Уже существуют, будут пропущены ({len(total_existing)}):")
        for n in total_existing:
            lines.append(f"  • {n}")
    if not total_new:
        lines.append("\n⚠ Нет новых плагинов для установки.")
    return "\n".join(lines)


def _upload_confirm_kb(pending: list) -> InlineKeyboardMarkup:
    total_new = sum(len(p["new"]) for p in pending)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ Установить ({total_new})" if total_new else "⚠ Нет новых",
                callback_data="plug:upload_confirm" if total_new else "plug:upload_cancel",
            ),
            InlineKeyboardButton(text="❌ Отменить", callback_data="plug:upload_cancel"),
        ],
    ])


async def _receive_and_preview(message: Message, state: FSMContext):
    doc = message.document
    filename = doc.file_name or "unknown"
    if not filename.lower().endswith(".jar"):
        await message.reply(
            f"⚠ <b>{filename}</b> — неподдерживаемый формат.\n"
            f"Принимаются только .jar файлы.",
            parse_mode="HTML",
        )
        return

    status_msg = await message.reply(f"⏳ Загружаю <b>{filename}</b>...", parse_mode="HTML")
    try:
        file = await message.bot.get_file(doc.file_id)
        bio = await message.bot.download_file(file.file_path)
        data = bio.read()

        preview = await plugin_manager.preview_upload(filename, data)
        if not preview["success"]:
            await status_msg.edit_text(
                f"❌ {preview.get('error', 'Ошибка')}", parse_mode="HTML"
            )
            return

        fsm_data = await state.get_data()
        pending = fsm_data.get("pending_uploads", [])
        pending.append({
            "tmp_path": preview["tmp_path"],
            "original_name": preview["original_name"],
            "is_archive": preview["is_archive"],
            "new": preview["new"],
            "existing": preview["existing"],
        })
        await state.update_data(pending_uploads=pending)
        await state.set_state(PluginState.waiting_upload_confirm)

        text = _build_preview_text(pending)
        text += "\n\nОтправь ещё файлы или подтверди установку."
        kb = _upload_confirm_kb(pending)
        await status_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Plugin upload error ({filename}): {e}")
        await status_msg.edit_text(
            f"❌ Ошибка загрузки {filename}: {e}", parse_mode="HTML"
        )


@plugins_router.message(StateFilter(PluginState.waiting_plugin_files), F.document)
async def upload_plugin_file(message: Message, state: FSMContext):
    await _receive_and_preview(message, state)


@plugins_router.message(StateFilter(PluginState.waiting_upload_confirm), F.document)
async def upload_more_plugin_files(message: Message, state: FSMContext):
    await _receive_and_preview(message, state)


@plugins_router.message(StateFilter(PluginState.waiting_search_query))
async def search_query_handler(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("Введи название плагина:")
        return
    await state.clear()
    await _show_search_results(message, state, query)
