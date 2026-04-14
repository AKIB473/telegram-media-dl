"""telegram-media-dl — Production-grade Telegram media downloader bot."""

__version__ = "1.0.0"
__author__ = "Akibuzzaman Akib"
__email__ = "akib473@github.com"
__license__ = "MIT"

from .bot import MediaDownloaderBot
from .config import config
from .downloader import Downloader
from .queue_manager import DownloadQueue

__all__ = [
    "MediaDownloaderBot",
    "config",
    "Downloader",
    "DownloadQueue",
]
