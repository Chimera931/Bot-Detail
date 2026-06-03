"""Info handler — directions."""

from aiogram import Router, F
from aiogram.types import Message

from config import YANDEX_MAPS_URL, ADMIN_PHONE
from keyboards import navigate_kb

router = Router()


@router.message(F.text == "📍 Как нас найти")
async def how_to_find_us(message: Message) -> None:
    await message.answer(
        "📍 <b>Как добраться до нас</b>\n\n"
        "Мы находимся в гараже. Нажмите кнопку ниже — откроется маршрут в Яндекс.Навигаторе.\n\n"
        f"По вопросам: <b>{ADMIN_PHONE}</b>",
        parse_mode="HTML",
        reply_markup=navigate_kb(YANDEX_MAPS_URL),
    )
