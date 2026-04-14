"""Aiogram 3 application entry point for telegram-media-dl."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from .config import settings
from .database import init_db
from .handlers import admin, commands, downloads
from .handlers import settings as settings_handler
from .middleware import RateLimitMiddleware, UserRegistrationMiddleware
from .queue_manager import DownloadQueue

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="start", description="Welcome screen"),
    BotCommand(command="help", description="Help & feature list"),
    BotCommand(command="search", description="Search YouTube"),
    BotCommand(command="history", description="Last 10 downloads"),
    BotCommand(command="settings", description="Preferences"),
    BotCommand(command="cancel", description="Cancel active downloads"),
]


async def on_startup(bot: Bot, queue: DownloadQueue) -> None:
    await init_db()
    await bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot started — polling…")


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    queue = DownloadQueue(settings.MAX_CONCURRENT)

    # Middleware (order matters: rate-limit first, then registration)
    rl_mw = RateLimitMiddleware(
        max_requests=settings.RATE_LIMIT_COUNT,
        window_seconds=settings.RATE_LIMIT_WINDOW,
    )
    dp.update.middleware(rl_mw)
    dp.update.middleware(UserRegistrationMiddleware())

    # Handlers
    commands.register(dp, queue)
    downloads.register(dp, queue, bot)
    admin.register(dp, queue, rl_mw.rate_limiter)
    settings_handler.register(dp)

    await on_startup(bot, queue)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
