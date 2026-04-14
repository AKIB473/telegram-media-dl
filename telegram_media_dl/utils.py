"""Utility functions for telegram-media-dl."""
import re
import os
import logging
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Supported site patterns
SUPPORTED_SITES = [
    r"(youtube\.com|youtu\.be)",
    r"instagram\.com",
    r"tiktok\.com",
    r"twitter\.com|x\.com",
    r"facebook\.com|fb\.watch",
    r"reddit\.com",
    r"twitch\.tv",
    r"vimeo\.com",
    r"dailymotion\.com",
    r"soundcloud\.com",
    r"spotify\.com",
    r"pinterest\.com",
    r"linkedin\.com",
    r"bilibili\.com",
    r"nicovideo\.jp",
    r"streamable\.com",
    r"streamja\.com",
    r"medal\.tv",
    r"gfycat\.com",
    r"imgur\.com",
    r"rumble\.com",
    r"odysee\.com",
    r"bitchute\.com",
    r"mixcloud\.com",
    r"bandcamp\.com",
]

SUPPORTED_PATTERN = re.compile(
    r"https?://(?:www\.)?" + "(?:" + "|".join(SUPPORTED_SITES) + ")",
    re.IGNORECASE,
)


def is_valid_url(url: str) -> bool:
    """Check if a URL is valid and from a supported site."""
    try:
        result = urlparse(url)
        if not all([result.scheme in ("http", "https"), result.netloc]):
            return False
        return bool(SUPPORTED_PATTERN.search(url))
    except Exception:
        return False


def is_generic_url(url: str) -> bool:
    """Check if a string is any valid URL (not just supported sites)."""
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def format_duration(seconds: Optional[int]) -> str:
    """Format seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def sanitize_filename(name: str) -> str:
    """Remove unsafe characters from filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(". ")
    return name[:200] if len(name) > 200 else name


def cleanup_file(path: Optional[str]) -> None:
    """Safely delete a file if it exists."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.debug("Cleaned up: %s", path)
        except OSError as e:
            logger.warning("Could not delete %s: %s", path, e)


def cleanup_dir_files(pattern: str) -> None:
    """Delete files matching a glob pattern."""
    from glob import glob
    for f in glob(pattern):
        cleanup_file(f)


def get_site_name(url: str) -> str:
    """Extract a friendly site name from URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        netloc = netloc.replace("www.", "")
        return netloc.split(".")[0].capitalize()
    except Exception:
        return "Unknown"


def build_info_message(info: dict) -> str:
    """Build a formatted info message from yt-dlp video info dict."""
    title = info.get("title", "Unknown")
    uploader = info.get("uploader") or info.get("channel", "Unknown")
    duration = format_duration(info.get("duration"))
    view_count = info.get("view_count")
    views = f"{view_count:,}" if view_count else "N/A"
    like_count = info.get("like_count")
    likes = f"{like_count:,}" if like_count else "N/A"
    description = (info.get("description") or "")[:200]
    if len(info.get("description") or "") > 200:
        description += "..."

    lines = [
        f"🎬 **{title}**",
        f"👤 {uploader}",
        f"⏱ Duration: `{duration}`",
        f"👁 Views: `{views}`",
        f"❤️ Likes: `{likes}`",
    ]
    if description:
        lines.append(f"\n📝 _{description}_")
    return "\n".join(lines)
