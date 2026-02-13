from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from utils.nav import main_menu_kb, show_menu, MENU_REPLY_KB
from utils.formatting import section_header

common_router = Router()

MAIN_MENU_TEXT = section_header(
    "🏠", "Главное меню",
    "Выбери раздел для управления сервером.",
)


@common_router.message(CommandStart())
async def cmd_start(message: Message):
    kb = await main_menu_kb(message.from_user.id)
    await message.answer(MAIN_MENU_TEXT, reply_markup=kb, parse_mode="HTML")
    # Send minimal reply KB as fallback
    await message.answer("Используй кнопки выше для навигации.", reply_markup=MENU_REPLY_KB)


@common_router.message(F.text.lower() == "📋 меню")
async def menu_fallback(message: Message):
    """Fallback for reply KB — send a fresh inline menu."""
    kb = await main_menu_kb(message.from_user.id)
    await message.answer(MAIN_MENU_TEXT, reply_markup=kb, parse_mode="HTML")


@common_router.callback_query(F.data == "nav:main")
async def nav_main(callback: CallbackQuery):
    kb = await main_menu_kb(callback.from_user.id)
    await show_menu(callback, MAIN_MENU_TEXT, kb)
    await callback.answer()


@common_router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"Твой ID: <code>{message.from_user.id}</code>")


@common_router.message()
async def catch_all(message: Message):
    """Catch any unhandled message — resend the main menu."""
    kb = await main_menu_kb(message.from_user.id)
    await message.answer(MAIN_MENU_TEXT, reply_markup=kb, parse_mode="HTML")
