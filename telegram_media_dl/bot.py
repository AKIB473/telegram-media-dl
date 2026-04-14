"""Main bot entrypoint for telegram-media-dl."""
import asyncio
import logging
import signal
import sys

from telethon import TelegramClient

from .config import config
from .handlers import BotHandlers

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("tmdl.log", encoding="utf-8"),
        ],
    )
    # Silence noisy libraries
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)


class MediaDownloaderBot:
    """The main bot class."""

    def __init__(self):
        config.validate()
        config.ensure_dirs()
        self.client = TelegramClient(
            config.SESSION_NAME,
            config.API_ID,
            config.API_HASH,
        )
        self.handlers: BotHandlers | None = None

    async def start(self) -> None:
        """Start the bot."""
        logger.info("Starting telegram-media-dl bot...")
        await self.client.start(bot_token=config.BOT_TOKEN)
        me = await self.client.get_me()
        logger.info("Bot started as @%s (ID: %d)", me.username, me.id)

        self.handlers = BotHandlers(self.client)
        logger.info(
            "Bot ready | Max concurrent: %d | Rate limit: %d/hour",
            config.MAX_CONCURRENT_DOWNLOADS,
            config.RATE_LIMIT_COUNT,
        )

        await self.client.run_until_disconnected()

    async def stop(self) -> None:
        """Gracefully stop the bot."""
        logger.info("Stopping bot...")
        if self.client.is_connected():
            await self.client.disconnect()
        logger.info("Bot stopped.")

    def run(self) -> None:
        """Run the bot with graceful shutdown handling."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def _handle_signal(sig):
            logger.info("Received signal %s, shutting down...", sig.name)
            loop.create_task(self.stop())

        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s))

        try:
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            loop.run_until_complete(self.stop())
            loop.close()
