"""My bookings handler."""

from aiogram import Router, F
from aiogram.types import Message

from config import ADMIN_PHONE, SERVICE_WASH, SERVICE_COMPLEX
from database import get_client_appointments
from utils import parse_dt, fmt_date_ru

router = Router()

SERVICE_LABELS = {
    SERVICE_WASH: "🚿 Детейлинг-мойка",
    SERVICE_COMPLEX: "🧹 Химчистка + мойка",
}


@router.message(F.text == "📋 Мои записи")
async def my_bookings(message: Message) -> None:
    appointments = await get_client_appointments(message.from_user.id)

    if not appointments:
        await message.answer(
            "У вас нет активных записей.\n\n"
            "Нажмите «📅 Записаться», чтобы забронировать время."
        )
        return

    lines = ["<b>Ваши активные записи:</b>\n"]
    for appt in appointments:
        start = parse_dt(appt["start_dt"])
        svc = SERVICE_LABELS.get(appt["service_type"], appt["service_type"])
        price = f"{appt['price']:,} ₽".replace(",", " ")
        lines.append(
            f"• {svc}\n"
            f"  📅 {fmt_date_ru(start)}\n"
            f"  💰 {price}\n"
        )

    lines.append(
        f"\nЧтобы отменить запись — позвоните нам:\n"
        f"📞 <b>{ADMIN_PHONE}</b>"
    )

    await message.answer("\n".join(lines), parse_mode="HTML")
