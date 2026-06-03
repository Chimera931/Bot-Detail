"""
Slot availability logic and formatting helpers.
All datetime objects are naive (local time, no timezone).
"""

from datetime import datetime, timedelta, date
from config import (
    WORK_START_HOUR, WORK_END_HOUR, SLOT_DURATION_HOURS,
    COMPLEX_DURATION_DAYS, BOOKING_HORIZON_DAYS,
    SERVICE_WASH, SERVICE_COMPLEX, BODY_CLASSES, PRICE_LABEL,
)
from database import get_appointments_in_range, get_blocks_in_range


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def fmt_date_ru(d: date | datetime) -> str:
    MONTHS = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    DAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    return f"{d.day} {MONTHS[d.month]} ({DAYS[d.weekday()]})"


def fmt_price(service: str, body_class: int) -> str:
    return PRICE_LABEL.get((service, body_class), "—")


def get_available_dates(service: str) -> list[date]:
    """
    Return list of calendar dates (within BOOKING_HORIZON_DAYS) on which
    the given service *might* have free slots (we check per-slot later).
    For wash: days that have at least one free 3-hour slot.
    For complex: start dates where 2 consecutive work days are not fully booked.
    """
    today = date.today()
    result = []
    for offset in range(1, BOOKING_HORIZON_DAYS + 1):
        d = today + timedelta(days=offset)
        if service == SERVICE_WASH:
            # quick pre-check: is the whole day blocked?
            result.append(d)
        else:
            # complex: we need d AND d+1
            if offset + 1 <= BOOKING_HORIZON_DAYS:
                result.append(d)
    return result


async def get_free_wash_slots(day: date) -> list[datetime]:
    """
    Return list of free slot start times for a wash on a given day.
    Slots: 07:00, 10:00, 13:00, 16:00 (3-hour blocks until 19:00).
    A slot is free if at least one line is free for its full duration.
    """
    slots = []
    h = WORK_START_HOUR
    while h + SLOT_DURATION_HOURS <= WORK_END_HOUR:
        slot_start = datetime(day.year, day.month, day.day, h, 0)
        slot_end = slot_start + timedelta(hours=SLOT_DURATION_HOURS)
        free = await _count_free_lines(slot_start, slot_end, SERVICE_WASH)
        if free > 0:
            slots.append(slot_start)
        h += SLOT_DURATION_HOURS
    return slots


async def get_free_complex_pairs(start_from: date) -> list[tuple[date, date]]:
    """
    Return list of (start_date, end_date) pairs for complex service.
    end_date = start_date + 1 day (2 working days).
    The pair is available if line 1 has no overlapping complex/wash for those 2 days.
    """
    today = date.today()
    horizon = today + timedelta(days=BOOKING_HORIZON_DAYS)
    d = start_from
    pairs = []
    while d < horizon:
        d_end = d + timedelta(days=COMPLEX_DURATION_DAYS - 1)
        if d_end > horizon:
            break
        slot_start = datetime(d.year, d.month, d.day, WORK_START_HOUR, 0)
        slot_end = datetime(d_end.year, d_end.month, d_end.day, WORK_END_HOUR, 0)
        # For complex we only use line 1
        free = await _count_free_lines(slot_start, slot_end, SERVICE_COMPLEX)
        if free > 0:
            pairs.append((d, d_end))  # show inclusive end
        d += timedelta(days=1)
    return pairs


async def _count_free_lines(
    slot_start: datetime, slot_end: datetime, service: str
) -> int:
    """
    Count how many lines are available for the given time range.
    Line 2 is only available for wash.
    """
    start_s = fmt_dt(slot_start)
    end_s = fmt_dt(slot_end)

    existing = await get_appointments_in_range(start_s, end_s)
    blocks = await get_blocks_in_range(start_s, end_s)

    if blocks:
        return 0  # any block closes all lines

    line1_busy = any(a["line_number"] == 1 for a in existing)
    line2_busy = any(a["line_number"] == 2 for a in existing)

    free = 0
    if not line1_busy:
        free += 1
    # Line 2 only for wash
    if service == SERVICE_WASH and not line2_busy:
        free += 1

    return free


async def assign_line(
    slot_start: datetime, slot_end: datetime, service: str
) -> int | None:
    """
    Return the line number to assign, or None if no lines are free.
    Prefer line 1 for complex, prefer line 2 for wash if line 1 is busy.
    """
    start_s = fmt_dt(slot_start)
    end_s = fmt_dt(slot_end)

    existing = await get_appointments_in_range(start_s, end_s)
    blocks = await get_blocks_in_range(start_s, end_s)

    if blocks:
        return None

    line1_busy = any(a["line_number"] == 1 for a in existing)
    line2_busy = any(a["line_number"] == 2 for a in existing)

    if not line1_busy:
        return 1
    if service == SERVICE_WASH and not line2_busy:
        return 2
    return None


def build_booking_summary(data: dict) -> str:
    """Build a formatted booking summary for client confirmation."""
    service_name = "🧹 Химчистка + мойка" if data["service"] == SERVICE_COMPLEX else "🚿 Детейлинг-мойка"
    return (
        f"<b>Ваша запись:</b>\n\n"
        f"🔧 Услуга: {service_name}\n"
        f"🚗 Машина: {data['car_brand']} ({data['car_body_name']})\n"
        f"🔢 Гос. номер: {data['plate_number']}\n"
        f"📅 Дата: {data['date_label']}\n"
        f"💰 Стоимость: {data['price_label']}\n"
    )


def build_admin_notification(data: dict, client: dict, line: int) -> str:
    """Build a notification message for the admin."""
    service_name = "🧹 Химчистка + мойка" if data["service"] == SERVICE_COMPLEX else "🚿 Детейлинг-мойка"
    username = f"@{client['username']}" if client.get("username") else "нет username"
    return (
        f"🆕 <b>Новая запись!</b>\n\n"
        f"👤 Имя TG: {username}\n"
        f"📞 Тел: {client['phone']}\n"
        f"🚗 Машина: {data['car_brand']} ({data['car_body_name']}, кл. {data['car_body_class']})\n"
        f"🔢 Гос. номер: {data['plate_number']}\n"
        f"🔧 Услуга: {service_name}\n"
        f"📅 Дата: {data['date_label']}\n"
        f"💰 Цена: {data['price_label']}\n"
        f"🔵 Линия: {line}\n"
    )


def build_reminder_message(appointment: dict) -> str:
    service_name = "🧹 Химчистка + мойка" if appointment["service_type"] == SERVICE_COMPLEX else "🚿 Детейлинг-мойка"
    start = parse_dt(appointment["start_dt"])
    return (
        f"⏰ <b>Напоминание о записи!</b>\n\n"
        f"Завтра мы начинаем работу с вашим автомобилем.\n\n"
        f"🔧 Услуга: {service_name}\n"
        f"🚗 {appointment['car_brand']} ({appointment['car_body_name']})\n"
        f"📅 Дата начала: {fmt_date_ru(start)}\n\n"
        f"Если возникли вопросы — позвоните нам 📞"
    )
