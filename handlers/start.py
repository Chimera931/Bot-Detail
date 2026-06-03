"""Start handler and main menu."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import ADMIN_ID
from keyboards import main_menu_kb, admin_panel_kb

router = Router()

WELCOME_TEXT = (
    "👋 Привет! Я бот <b>Детейлинг-гараж</b>.\n\n"
    "Здесь вы можете:\n"
    "• 📅 Записаться на детейлинг-мойку или химчистку\n"
    "• 📋 Посмотреть свои активные записи\n"
    "• 📍 Узнать, как к нам добраться\n\n"
    "Выберите действие ниже 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "⭐ Распознан аккаунт администратора.\n\n"
            "Вы можете управлять записями и блокировками через визуальный календарь:",
            reply_markup=admin_panel_kb()
        )

