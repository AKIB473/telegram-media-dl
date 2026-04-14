"""Download engine using yt-dlp for telegram-media-dl."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import yt_dlp

from .config import settings
from .utils import format_size, make_progress_bar, sanitize_filename

logger = logging.getLogger(__name__)

QUALITY_FORMATS: Dict[str, str] = {
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
    """Raised when the file exceeds the configured size limit."""


def get_video_info(url: str) -> Dict[str, Any]:
    """Fetch video metadata without downloading."""
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": not settings.ALLOW_PLAYLISTS,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info or {}


def check_file_size(info: Dict[str, Any]) -> Optional[int]:
    """
    Return file size in bytes if available, else None.
    Raises :exc:`FileTooLargeError` when the size exceeds the limit.
    """
    size = info.get("filesize") or info.get("filesize_approx")
    if size:
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if size > max_bytes:
            raise FileTooLargeError(
                f"File is too large ({format_size(size)}). "
                f"Maximum allowed: {settings.MAX_FILE_SIZE_MB} MB"
            )
    return size


class Downloader:
    """Handles downloading media via yt-dlp with optional progress callbacks."""

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.download_dir = download_dir or settings.DOWNLOAD_DIR
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        self.on_progress = on_progress
        self.on_status = on_status
        self._last_progress_time = 0.0

    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """Called by yt-dlp during download to relay progress."""
        status = d.get("status")
        now = time.monotonic()

        if status == "downloading":
            # Throttle to once every 2 seconds
            if now - self._last_progress_time < 2.0:
                return
            self._last_progress_time = now

            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            speed = (d.get("_speed_str") or "?/s").strip()
            eta = (d.get("_eta_str") or "?").strip()

            if total and total > 0:
                percent = downloaded / total * 100
                bar = make_progress_bar(percent)
            else:
                percent_str = (d.get("_percent_str") or "?%").strip()
                bar = f"📥 {percent_str}"

            msg = f"{bar}"
            if speed and speed != "Unknown B/s":
                msg += f" • {speed}"
            if eta and eta not in ("Unknown", "?"):
                msg += f" • ETA {eta}"
            if total:
                msg += f"\n`{format_size(downloaded)} / {format_size(total)}`"

            if self.on_progress:
                self.on_progress(msg)

        elif status == "finished":
            if self.on_status:
                self.on_status("📤 Processing & uploading…")

    def _build_ydl_opts(
        self,
        format_choice: str,
        quality: str,
        job_id: str,
    ) -> Dict[str, Any]:
        """Assemble the yt-dlp options dict for a download job."""
        safe_job_id = sanitize_filename(job_id)
        output_template = str(
            Path(self.download_dir) / f"{safe_job_id}_%(title).80s.%(ext)s"
        )

        is_audio = format_choice == "audio"
        fmt = QUALITY_FORMATS.get(
            "audio" if is_audio else quality,
            QUALITY_FORMATS["best"],
        )

        opts: Dict[str, Any] = {
            "outtmpl": output_template,
            "format": fmt,
            "progress_hooks": [self._progress_hook],
            "noplaylist": not settings.ALLOW_PLAYLISTS,
            "quiet": True,
            "no_warnings": True,
            "retries": settings.MAX_RETRIES,
            "fragment_retries": settings.MAX_RETRIES,
            "concurrent_fragment_downloads": 4,
            "merge_output_format": "mp4",
            # Subtitle support
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            # Metadata & thumbnail embedding
            "addmetadata": True,
            "embedthumbnail": True,
            # Chapter markers
            "addchapters": True,
        }

        # Cookie file for age-restricted content
        if settings.COOKIE_FILE and os.path.exists(settings.COOKIE_FILE):
            opts["cookiefile"] = settings.COOKIE_FILE

        if is_audio:
            audio_quality = quality if quality in AUDIO_QUALITIES else settings.DEFAULT_AUDIO_QUALITY
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                },
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ]
        else:
            opts["postprocessors"] = [
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail", "already_have_thumbnail": False},
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
        Download media from *url*.

        Returns ``(filepath, info_dict)``.
        Raises :exc:`DownloadError` on failure.
        """
        loop = asyncio.get_event_loop()

        def _run() -> Tuple[str, Dict[str, Any]]:
            self._last_progress_time = 0.0
            opts = self._build_ydl_opts(format_choice, quality, job_id)

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise DownloadError("yt-dlp returned no info")

                check_file_size(info)

                filepath = ydl.prepare_filename(info)

                # For audio jobs the extension changes after post-processing
                if format_choice == "audio":
                    base, _ = os.path.splitext(filepath)
                    filepath = base + ".mp3"

                # Fallback: find newest matching file in the download dir
                if not os.path.exists(filepath):
                    safe_job_id = sanitize_filename(job_id)
                    candidates = sorted(
                        Path(self.download_dir).glob(f"{safe_job_id}_*"),
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
                timeout=settings.DOWNLOAD_TIMEOUT,
            )
            return filepath, info
        except asyncio.TimeoutError:
            raise DownloadError(
                f"Download timed out after {settings.DOWNLOAD_TIMEOUT}s"
            )
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadError(str(exc)) from exc
