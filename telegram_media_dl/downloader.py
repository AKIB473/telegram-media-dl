"""Download engine using yt-dlp for telegram-media-dl."""
import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import yt_dlp

from .config import config
from .utils import format_size, sanitize_filename

logger = logging.getLogger(__name__)

QUALITY_FORMATS = {
    "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
    "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
    "480p":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
    "360p":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
    "audio": "bestaudio/best",
}

AUDIO_QUALITIES = {"320", "256", "192", "128", "96"}


class DownloadError(Exception):
    """Raised when a download fails."""


class FileTooLargeError(DownloadError):
    """Raised when the file exceeds the size limit."""


def get_video_info(url: str) -> Dict[str, Any]:
    """Fetch video metadata without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": not config.ALLOW_PLAYLISTS,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info or {}


def check_file_size(info: Dict[str, Any]) -> Optional[int]:
    """
    Return file size in bytes if available, or None.
    Raises FileTooLargeError if the size exceeds the configured limit.
    """
    size = info.get("filesize") or info.get("filesize_approx")
    if size:
        max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
        if size > max_bytes:
            raise FileTooLargeError(
                f"File is too large ({format_size(size)}). "
                f"Maximum allowed: {config.MAX_FILE_SIZE_MB} MB"
            )
    return size


class Downloader:
    """Handles downloading media via yt-dlp with progress callbacks."""

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self.download_dir = download_dir or config.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.on_progress = on_progress
        self.on_status = on_status
        self._last_progress_time = 0.0

    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """Called by yt-dlp during download."""
        status = d.get("status")
        now = time.monotonic()

        if status == "downloading":
            # Throttle progress updates to every 2 seconds
            if now - self._last_progress_time < 2.0:
                return
            self._last_progress_time = now

            percent = d.get("_percent_str", "?%").strip()
            speed = d.get("_speed_str", "?/s").strip()
            eta = d.get("_eta_str", "?").strip()
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)

            msg = f"📥 {percent}"
            if speed and speed != "Unknown B/s":
                msg += f" • {speed}"
            if eta and eta != "Unknown":
                msg += f" • ETA {eta}"
            if total:
                msg += f"\n`{format_size(downloaded)} / {format_size(total)}`"

            if self.on_progress:
                self.on_progress(msg)

        elif status == "finished":
            if self.on_status:
                self.on_status("📤 Processing & uploading...")

    def _build_ydl_opts(
        self,
        format_choice: str,
        quality: str,
        job_id: str,
    ) -> Dict[str, Any]:
        """Build yt-dlp options dict."""
        safe_job_id = sanitize_filename(job_id)
        output_template = str(
            self.download_dir / f"{safe_job_id}_%(title).80s.%(ext)s"
        )

        is_audio = format_choice == "audio"
        fmt = QUALITY_FORMATS.get(quality if not is_audio else "audio", QUALITY_FORMATS["best"])

        opts: Dict[str, Any] = {
            "outtmpl": output_template,
            "format": fmt,
            "progress_hooks": [self._progress_hook],
            "noplaylist": not config.ALLOW_PLAYLISTS,
            "quiet": True,
            "no_warnings": True,
            "retries": config.MAX_RETRIES,
            "fragment_retries": config.MAX_RETRIES,
            "concurrent_fragment_downloads": 4,
            "merge_output_format": "mp4",
        }

        if is_audio:
            audio_quality = quality if quality in AUDIO_QUALITIES else config.DEFAULT_AUDIO_QUALITY
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }
            ]

        return opts

    async def download(
        self,
        url: str,
        format_choice: str = "video",
        quality: str = "best",
        job_id: str = "download",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Download media from URL.

        Returns (filepath, info_dict).
        Raises DownloadError on failure.
        """
        loop = asyncio.get_event_loop()

        def _run() -> Tuple[str, Dict[str, Any]]:
            self._last_progress_time = 0.0
            opts = self._build_ydl_opts(format_choice, quality, job_id)

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise DownloadError("yt-dlp returned no info")

                # Check size limit (approximate — actual may vary)
                check_file_size(info)

                # Determine actual output file path
                filepath = ydl.prepare_filename(info)

                # For audio, the extension changes after post-processing
                if format_choice == "audio":
                    base, _ = os.path.splitext(filepath)
                    filepath = base + ".mp3"

                # Fallback: scan download dir for the newest matching file
                if not os.path.exists(filepath):
                    safe_job_id = sanitize_filename(job_id)
                    candidates = sorted(
                        self.download_dir.glob(f"{safe_job_id}_*"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    if candidates:
                        filepath = str(candidates[0])

                if not os.path.exists(filepath):
                    raise DownloadError("Downloaded file not found on disk")

                return filepath, info

        try:
            filepath, info = await asyncio.wait_for(
                loop.run_in_executor(None, _run),
                timeout=config.DOWNLOAD_TIMEOUT,
            )
            return filepath, info
        except asyncio.TimeoutError:
            raise DownloadError(
                f"Download timed out after {config.DOWNLOAD_TIMEOUT}s"
            )
        except yt_dlp.utils.DownloadError as e:
            raise DownloadError(str(e)) from e
