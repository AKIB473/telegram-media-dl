"""Configuration management for telegram-media-dl."""
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load .env from current directory or parent
load_dotenv()


class Config:
    """Central configuration loaded from environment variables."""

    # --- Telegram ---
    _api_id_raw = os.getenv("API_ID", "0")
    API_ID: int = int(_api_id_raw) if _api_id_raw.isdigit() else 0
    API_HASH: str = os.getenv("API_HASH", "")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # --- Admin ---
    ADMIN_IDS: List[int] = [
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "").split(",")
        if x.strip().isdigit()
    ]

    # --- Download settings ---
    DOWNLOAD_DIR: Path = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "1900"))  # Telegram limit ~2GB
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
    DEFAULT_VIDEO_QUALITY: str = os.getenv("DEFAULT_VIDEO_QUALITY", "best")
    DEFAULT_AUDIO_QUALITY: str = os.getenv("DEFAULT_AUDIO_QUALITY", "192")
    DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT", "300"))  # seconds

    # --- Rate limiting ---
    RATE_LIMIT_COUNT: int = int(os.getenv("RATE_LIMIT_COUNT", "5"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # seconds

    # --- Features ---
    ALLOW_PLAYLISTS: bool = os.getenv("ALLOW_PLAYLISTS", "false").lower() == "true"
    SEND_THUMBNAIL: bool = os.getenv("SEND_THUMBNAIL", "true").lower() == "true"
    SHOW_VIDEO_INFO: bool = os.getenv("SHOW_VIDEO_INFO", "true").lower() == "true"
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # --- Session ---
    SESSION_NAME: str = os.getenv("SESSION_NAME", "tmdl_bot")

    @classmethod
    def validate(cls) -> None:
        """Raise ValueError if required config is missing."""
        errors = []
        if not cls.API_ID:
            errors.append("API_ID is required")
        if not cls.API_HASH:
            errors.append("API_HASH is required")
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        if errors:
            raise ValueError(
                "Missing required configuration:\n" + "\n".join(f"  - {e}" for e in errors)
            )

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create required directories."""
        cls.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
