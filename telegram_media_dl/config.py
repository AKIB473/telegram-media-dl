"""Configuration module for telegram-media-dl using pydantic-settings."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Required
    BOT_TOKEN: str = "placeholder"

    # Optional
    ADMIN_IDS: List[int] = []
    TARGET_CHAT: Optional[str] = None
    DOWNLOAD_DIR: Path = Path("downloads")
    MAX_FILE_SIZE_MB: int = 1900
    MAX_CONCURRENT: int = 3
    RATE_LIMIT_COUNT: int = 5
    RATE_LIMIT_WINDOW: int = 3600
    ALLOW_PLAYLISTS: bool = False
    SEND_THUMBNAIL: bool = True
    DOWNLOAD_TIMEOUT: int = 300
    MAX_RETRIES: int = 3
    DB_PATH: Path = Path("tmdl.db")
    LOG_LEVEL: str = "INFO"
    DEFAULT_AUDIO_QUALITY: str = "192"
    COOKIE_FILE: Optional[str] = None


settings = Settings()
