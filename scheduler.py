"""APScheduler — daily reminder job for clients."""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from database import get_pending_reminders, mark_reminded
from utils import build_reminder_message, fmt_dt

logger = logging.getLogger(__name__)


async def send_reminders(bot: Bot) -> None:
    """
    Send reminder to clients whose work starts tomorrow.
    Runs every morning at 09:00 local time.
    """
    tomorrow = datetime.now().date() + timedelta(days=1)
    tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
    tomorrow_end = datetime.combine(tomorrow, datetime.max.time())

    appointments = await get_pending_reminders(
        reminder_before_dt=fmt_dt(tomorrow_end),
        now_dt=fmt_dt(tomorrow_start),
    )

    for appt in appointments:
        try:
            text = build_reminder_message(appt)
            await bot.send_message(
                chat_id=appt["client_id"],
                text=text,
                parse_mode="HTML"
            )
            await mark_reminded(appt["id"])
            logger.info(f"Reminder sent to client {appt['client_id']} for appt {appt['id']}")
        except Exception as e:
            logger.error(f"Failed to send reminder to {appt['client_id']}: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    from pytz import timezone
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=9, minute=0, timezone=timezone("Europe/Moscow")),
        args=[bot],
        id="daily_reminders",
        replace_existing=True,
    )
    return scheduler
