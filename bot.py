"""Entry point — initialize bot, register routers, start polling."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import BOT_TOKEN
from database import init_db
from scheduler import setup_scheduler
from handlers import start, booking, my_bookings, info, admin
from api import create_api_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    # Init DB
    await init_db()
    logger.info("Database initialized.")

    # Bot & Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers (order matters — admin before generic)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(my_bookings.router)
    dp.include_router(info.router)

    # Scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started.")

    # API App Web Server Setup
    import os
    port = int(os.environ.get("PORT", 8080))
    api_app = create_api_app()
    runner = web.AppRunner(api_app)
    await runner.setup()
    # API runs on port 8080 or port assigned by Render
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"API Server started on port {port}.")

    # Start polling
    logger.info("Bot started. Polling...")
    try:
        # Run polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await runner.cleanup()
        await bot.session.close()
        logger.info("Bot and API Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())

