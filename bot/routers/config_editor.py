from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from core.config import config as app_config
from minecraft.server_config import (
    server_config,
    EDITABLE_PROPERTIES,
    TEMPLATES,
    PROPERTY_CATEGORIES,
)
from states.states import ConfigState
from utils.formatting import section_header, success_text, error_text
from utils.logger import logger
from utils.nav import check_admin, show_menu, back_row, return_to_menu, CANCEL_REPLY_KB

config_router = Router()

CONFIG_MENU_TEXT = section_header(
    "⚙", "Настройки сервера",
    "Редактирование server.properties.\nВыбери категорию или примени шаблон.",
)


def _config_main_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📋 Показать конфиг", callback_data="cfg:show")],
        [InlineKeyboardButton(text="ℹ Информация о сервере", callback_data="cfg:info")],
    ]
    cat_row = []
    for key, cat in PROPERTY_CATEGORIES.items():
        cat_row.append(
            InlineKeyboardButton(text=cat["label"], callback_data=f"cfg:cat:{key}")
        )
        if len(cat_row) == 2:
            buttons.append(cat_row)
            cat_row = []
    if cat_row:
        buttons.append(cat_row)

    buttons.append([InlineKeyboardButton(text="📄 Шаблоны", callback_data="cfg:templates")])
    buttons.append(back_row("main"))
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _prop_value_kb(prop_name: str, current_value: str) -> InlineKeyboardMarkup:
    """Build inline KB with value buttons based on property type."""
    meta = EDITABLE_PROPERTIES.get(prop_name, {})
    prop_type = meta.get("type", "text")
    buttons = []

    if prop_type == "bool":
        row = []
        for val, label in [("true", "✅ Вкл"), ("false", "❌ Выкл")]:
            text = f"{label} •" if current_value == val else label
            row.append(InlineKeyboardButton(
                text=text, callback_data=f"cfg:set:{prop_name}:{val}"
            ))
        buttons.append(row)

    elif prop_type == "enum":
        values = meta.get("values", [])
        labels = meta.get("labels", values)
        for val, label in zip(values, labels):
            text = f"{label} •" if current_value == val else label
            buttons.append([InlineKeyboardButton(
                text=text, callback_data=f"cfg:set:{prop_name}:{val}"
            )])

    elif prop_type == "range":
        presets = meta.get("presets", [])
        row = []
        for val, label in presets:
            text = f"[{label}]" if current_value == val else label
            row.append(InlineKeyboardButton(
                text=text, callback_data=f"cfg:set:{prop_name}:{val}"
            ))
            if len(row) >= 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton(
            text="✏ Ввести вручную", callback_data=f"cfg:input:{prop_name}"
        )])

    else:  # text
        buttons.append([InlineKeyboardButton(
            text="✏ Ввести значение", callback_data=f"cfg:input:{prop_name}"
        )])

    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="cfg:back_cat")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_category(callback: CallbackQuery, state: FSMContext, cat_key: str, cat: dict):
    """Display a property category with its editable properties."""
    await state.update_data(current_category=cat_key)
    props = server_config.read_properties()
    buttons = []
    lines = [f"<b>{cat['label']}</b>", f"{cat['desc']}\n"]
    for prop_name in cat["properties"]:
        val = props.get(prop_name, "не задано")
        meta = EDITABLE_PROPERTIES.get(prop_name, {})
        desc = meta.get("desc", prop_name) if isinstance(meta, dict) else prop_name
        lines.append(f"<code>{prop_name}</code> = <b>{val}</b>")
        buttons.append([
            InlineKeyboardButton(
                text=f"✏ {desc}: {val}",
                callback_data=f"cfg:prop:{prop_name}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="cfg:back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await show_menu(callback, "\n".join(lines), kb)


@config_router.callback_query(F.data == "nav:config")
async def config_menu(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await show_menu(callback, CONFIG_MENU_TEXT, _config_main_kb())
    await callback.answer()


@config_router.callback_query(F.data.startswith("cfg:"))
async def config_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return

    parts = callback.data.split(":")
    action = parts[1]

    if action == "show":
        await callback.answer()
        summary = server_config.get_editable_summary()
        if not summary:
            summary = "server.properties не найден. Сервер ещё не запускался?"
        await show_menu(callback, summary, _config_main_kb())

    elif action == "info":
        await callback.answer()
        text = (
            "<b>ℹ Информация о сервере</b>\n\n"
            f"Версия MC: <b>{app_config.mc_version}</b>\n"
            f"Тип: <b>{app_config.mc_type}</b>\n"
            f"Лоадер: <b>{app_config.mc_loader}</b>\n"
            f"RAM: <b>{app_config.mc_memory}</b>\n"
            f"Контейнер: <code>{app_config.mc_container_name}</code>\n\n"
            "<i>Эти параметры задаются в docker-compose.yml</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data="cfg:back")],
        ])
        await show_menu(callback, text, kb)

    elif action == "cat":
        cat_key = parts[2]
        cat = PROPERTY_CATEGORIES.get(cat_key)
        if not cat:
            await callback.answer("Категория не найдена")
            return
        await callback.answer()
        await _show_category(callback, state, cat_key, cat)

    elif action == "prop":
        prop_name = parts[2]
        await callback.answer()
        meta = EDITABLE_PROPERTIES.get(prop_name, {})
        desc = meta.get("desc", prop_name) if isinstance(meta, dict) else prop_name
        current = server_config.get_property(prop_name) or "не задано"

        text = (
            f"<b>{prop_name}</b>\n"
            f"{desc}\n\n"
            f"Текущее значение: <b>{current}</b>"
        )
        kb = _prop_value_kb(prop_name, current)
        await show_menu(callback, text, kb)

    elif action == "set":
        prop_name = parts[2]
        value = ":".join(parts[3:])
        await callback.answer()

        ok = server_config.write_property(prop_name, value)
        if ok:
            logger.info(f"Config changed [{callback.from_user.id}]: {prop_name}={value}")
            text = success_text(
                f"<code>{prop_name}</code> = <b>{value}</b>\n"
                f"Перезапусти сервер для применения."
            )
        else:
            text = error_text("Не удалось изменить. server.properties не найден?")

        current = server_config.get_property(prop_name) or value
        meta = EDITABLE_PROPERTIES.get(prop_name, {})
        desc = meta.get("desc", prop_name) if isinstance(meta, dict) else prop_name
        full_text = (
            f"{text}\n\n"
            f"<b>{prop_name}</b>\n"
            f"{desc}\n\n"
            f"Текущее значение: <b>{current}</b>"
        )
        kb = _prop_value_kb(prop_name, current)
        await show_menu(callback, full_text, kb)

    elif action == "input":
        prop_name = parts[2]
        await callback.answer()
        meta = EDITABLE_PROPERTIES.get(prop_name, {})
        desc = meta.get("desc", prop_name) if isinstance(meta, dict) else prop_name
        current = server_config.get_property(prop_name) or "не задано"

        range_hint = ""
        if isinstance(meta, dict) and meta.get("type") == "range":
            range_hint = f"\nДопустимый диапазон: {meta.get('min', '?')} — {meta.get('max', '?')}"

        await state.update_data(editing_property=prop_name)
        await state.set_state(ConfigState.waiting_value)
        await callback.message.answer(
            f"Свойство: <code>{prop_name}</code>\n"
            f"{desc}\n"
            f"Текущее значение: <b>{current}</b>{range_hint}\n\n"
            f"Введи новое значение:",
            reply_markup=CANCEL_REPLY_KB,
        )

    elif action == "templates":
        await callback.answer()
        buttons = []
        lines = ["<b>📄 Шаблоны</b>\n",
                 "Быстрое применение набора настроек.\n"]
        for name, tmpl in TEMPLATES.items():
            label = tmpl.get("label", name.title())
            desc = tmpl.get("desc", "")
            lines.append(f"<b>{label}</b>")
            if desc:
                lines.append(f"  {desc}")
            lines.append("")
            buttons.append([
                InlineKeyboardButton(text=label, callback_data=f"cfg:template:{name}")
            ])
        buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="cfg:back")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await show_menu(callback, "\n".join(lines), kb)

    elif action == "template":
        template_name = parts[2]
        await callback.answer()
        result = server_config.apply_template(template_name)
        if "error" in result:
            text = error_text(result["error"])
        else:
            label = TEMPLATES.get(template_name, {}).get("label", template_name)
            changes = "\n".join(f"  <code>{k}</code> = {v}" for k, v in result.items())
            text = success_text(
                f"Шаблон <b>{label}</b> применён!\n\n"
                f"{changes}\n\n"
                f"Перезапусти сервер для применения."
            )
        await show_menu(callback, text, _config_main_kb())

    elif action == "back_cat":
        await callback.answer()
        data = await state.get_data()
        cat_key = data.get("current_category")
        if cat_key and cat_key in PROPERTY_CATEGORIES:
            await _show_category(callback, state, cat_key, PROPERTY_CATEGORIES[cat_key])
        else:
            await show_menu(callback, CONFIG_MENU_TEXT, _config_main_kb())

    elif action == "back":
        await callback.answer()
        await show_menu(callback, CONFIG_MENU_TEXT, _config_main_kb())


@config_router.message(
    F.text.lower().in_({"◀ отмена", "cancel"}),
    StateFilter(ConfigState.waiting_value),
)
async def cancel_config(message: Message, state: FSMContext):
    await state.clear()
    await return_to_menu(message)


@config_router.message(StateFilter(ConfigState.waiting_value))
async def process_config_value(message: Message, state: FSMContext):
    data = await state.get_data()
    prop_name = data.get("editing_property")
    if not prop_name:
        await state.clear()
        return

    value = message.text.strip()

    meta = EDITABLE_PROPERTIES.get(prop_name, {})
    if isinstance(meta, dict) and meta.get("type") == "range":
        try:
            num = int(value)
            min_val = meta.get("min", 0)
            max_val = meta.get("max", 999)
            if num < min_val or num > max_val:
                await message.answer(f"Значение должно быть от {min_val} до {max_val}. Попробуй ещё:")
                return
        except ValueError:
            await message.answer("Введи число:")
            return

    ok = server_config.write_property(prop_name, value)

    if ok:
        logger.info(f"Config changed [{message.from_user.id}]: {prop_name}={value}")
        text = success_text(
            f"Свойство <code>{prop_name}</code> изменено на <b>{value}</b>.\n"
            f"Перезапусти сервер для применения."
        )
    else:
        text = error_text("Не удалось изменить свойство. server.properties не найден?")

    await state.clear()
    await message.answer(text)
    await message.answer(CONFIG_MENU_TEXT, reply_markup=_config_main_kb(), parse_mode="HTML")
