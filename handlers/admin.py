"""
Admin commands:
  /block [date] [HH:MM HH:MM]  — block a day or specific slot
  /unblock [date]               — remove all blocks on a date
  /schedule                     — show next 7 days of appointments
  /clients                      — list all clients in DB
"""

import logging
from datetime import datetime, date, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_ID, SERVICE_WASH, SERVICE_COMPLEX
from database import (
    add_block, remove_blocks_on_date,
    get_appointments_for_schedule, get_all_clients,
)
from utils import fmt_date_ru, parse_dt

logger = logging.getLogger(__name__)
router = Router()

SERVICE_LABELS = {
    SERVICE_WASH: "Мойка",
    SERVICE_COMPLEX: "Химчистка",
}


def is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID


@router.message(Command("admin"))
@router.message(Command("panel"))
async def cmd_admin_panel(message: Message) -> None:
    if not is_admin(message):
        return
    from keyboards import admin_panel_kb
    await message.answer(
        "👋 Добро пожаловать в админ-панель!\n\n"
        "Нажмите кнопку ниже, чтобы открыть интерактивное расписание с возможностью блокировки времени.",
        reply_markup=admin_panel_kb()
    )


# ─── /block ────────────────────────────────────────────────────────────────

@router.message(Command("block"))
async def cmd_block(message: Message) -> None:
    if not is_admin(message):
        return

    args = message.text.split()[1:]  # everything after /block

    # Usage:
    #   /block 2026-06-10             → block whole day (07:00–19:00)
    #   /block 2026-06-10 10:00 13:00 → block specific slot

    if not args:
        await message.answer(
            "Использование:\n"
            "<code>/block 2026-06-10</code> — закрыть весь день\n"
            "<code>/block 2026-06-10 10:00 13:00</code> — закрыть слот",
            parse_mode="HTML",
        )
        return

    try:
        date_str = args[0]
        d = date.fromisoformat(date_str)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД (например: 2026-06-10)")
        return

    if len(args) == 1:
        # Block whole day
        start_dt = datetime(d.year, d.month, d.day, 7, 0).strftime("%Y-%m-%d %H:%M")
        end_dt = datetime(d.year, d.month, d.day, 19, 0).strftime("%Y-%m-%d %H:%M")
        reason = "Выходной / личные дела"
    elif len(args) == 3:
        # Block specific slot
        try:
            start_dt = datetime.strptime(f"{date_str} {args[1]}", "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{date_str} {args[2]}", "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
            reason = "Занято"
        except ValueError:
            await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 10:00 13:00)")
            return
    else:
        await message.answer("❌ Неверное количество аргументов. Смотрите /block без аргументов для справки.")
        return

    await add_block(start_dt, end_dt, reason)
    await message.answer(f"✅ Заблокировано: {date_str} с {start_dt[11:]} до {end_dt[11:]}")


# ─── /unblock ──────────────────────────────────────────────────────────────

@router.message(Command("unblock"))
async def cmd_unblock(message: Message) -> None:
    if not is_admin(message):
        return

    args = message.text.split()[1:]
    if not args:
        await message.answer("Использование: <code>/unblock 2026-06-10</code>", parse_mode="HTML")
        return

    try:
        date_str = args[0]
        date.fromisoformat(date_str)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД")
        return

    count = await remove_blocks_on_date(date_str)
    if count:
        await message.answer(f"✅ Снято блокировок: {count} на {date_str}")
    else:
        await message.answer(f"ℹ️ Блокировок на {date_str} не найдено.")


# ─── /schedule ─────────────────────────────────────────────────────────────

@router.message(Command("schedule"))
async def cmd_schedule(message: Message) -> None:
    if not is_admin(message):
        return

    appointments = await get_appointments_for_schedule(days=7)

    if not appointments:
        await message.answer("📅 Записей на ближайшие 7 дней нет.")
        return

    lines = ["<b>📅 Расписание на 7 дней:</b>\n"]
    for appt in appointments:
        start = parse_dt(appt["start_dt"])
        svc = SERVICE_LABELS.get(appt["service_type"], "?")
        price = f"{appt['price']:,} ₽".replace(",", " ")
        lines.append(
            f"• <b>{fmt_date_ru(start)}</b> {start.strftime('%H:%M')}\n"
            f"  {svc} · Линия {appt['line_number']} · {price}\n"
            f"  ID клиента: {appt['client_id']}\n"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── /clients ──────────────────────────────────────────────────────────────

@router.message(Command("clients"))
async def cmd_clients(message: Message) -> None:
    if not is_admin(message):
        return

    clients = await get_all_clients()

    if not clients:
        await message.answer("База клиентов пуста.")
        return

    lines = [f"<b>👥 Клиентов в базе: {len(clients)}</b>\n"]
    for i, c in enumerate(clients, 1):
        lines.append(
            f"{i}. {c.get('car_brand', '—')} {c.get('car_body_name', '')} "
            f"({c.get('plate_number', '—')})\n"
            f"   📞 {c.get('phone', '—')}\n"
        )
        # Split into chunks of 20 to avoid Telegram message limit
        if i % 20 == 0:
            await message.answer("\n".join(lines), parse_mode="HTML")
            lines = []

    if lines:
        await message.answer("\n".join(lines), parse_mode="HTML")
