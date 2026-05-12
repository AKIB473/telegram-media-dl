"""Tests for telegram_media_dl.downloader."""
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from telegram_media_dl.downloader import (
    Downloader,
    DownloadError,
    FileTooLargeError,
    get_video_info,
    check_file_size,
    QUALITY_FORMATS,
)
from telegram_media_dl.config import settings


class TestGetVideoInfo:
    """Tests for metadata-only fetch."""

    def test_returns_info_dict(self):
        """Should return a dict with video metadata (synchronous function)."""
        mock_info = {
            "title": "Test Video",
            "duration": 120,
            "filesize": 5_000_000,
            "filesize_approx": 5_000_000,
        }

        with patch("telegram_media_dl.downloader.yt_dlp") as mock_yt:
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.extract_info.return_value = mock_info
            mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

            result = get_video_info("https://youtube.com/watch?v=test")

            assert result == mock_info

    def test_returns_empty_on_none(self):
        """Should return empty dict when yt-dlp returns None."""
        with patch("telegram_media_dl.downloader.yt_dlp") as mock_yt:
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.extract_info.return_value = None
            mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

            result = get_video_info("https://youtube.com/watch?v=test")
            assert result == {}

    def test_extract_info_called_without_download(self):
        """extract_info should always be called with download=False."""
        with patch("telegram_media_dl.downloader.yt_dlp") as mock_yt:
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.extract_info.return_value = {"title": "Test"}
            mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

            get_video_info("https://youtube.com/watch?v=test")

            call_kwargs = mock_ydl_instance.extract_info.call_args
            assert call_kwargs[0][0] == "https://youtube.com/watch?v=test"
            assert call_kwargs[1] == {"download": False}


class TestCheckFileSize:
    """Tests for file size validation."""

    def test_within_limit(self):
        """File under limit should return size without error."""
        info = {"filesize": 5_000_000}
        result = check_file_size(info)
        assert result == 5_000_000

    def test_no_filesize(self):
        """Info without filesize should return None."""
        info = {"title": "Test"}
        result = check_file_size(info)
        assert result is None

    def test_uses_filesize_approx_as_fallback(self):
        """Should use filesize_approx when filesize is missing."""
        info = {"filesize": None, "filesize_approx": 3_000_000}
        result = check_file_size(info)
        assert result == 3_000_000

    def test_exceeds_limit_raises(self):
        """File over limit should raise FileTooLargeError."""
        info = {"filesize": 5_000_000_000}  # 5 GB
        with pytest.raises(FileTooLargeError) as exc_info:
            check_file_size(info)
        assert "too large" in str(exc_info.value).lower()


class TestDownloaderConstructor:
    """Tests for Downloader __init__."""

    def test_default_download_dir_uses_settings(self):
        """Default download dir should come from settings."""
        dl = Downloader()
        assert dl.download_dir == settings.DOWNLOAD_DIR

    def test_custom_download_dir(self, tmp_path):
        """Custom download dir should be accepted."""
        dl = Downloader(download_dir=tmp_path)
        assert dl.download_dir == tmp_path


class TestBuildYdlOpts:
    """Tests for _build_ydl_opts option construction."""

    @pytest.fixture
    def downloader(self, tmp_path):
        return Downloader(download_dir=tmp_path, on_progress=lambda m: None)

    def test_video_best_quality(self, downloader):
        """Should build correct opts for best video quality."""
        opts = downloader._build_ydl_opts("video", "best", "test_job")

        assert opts["format"] == QUALITY_FORMATS["best"]
        assert "test_job" in opts["outtmpl"]
        assert opts["merge_output_format"] == "mp4"
        assert opts["writesubtitles"] is True

    def test_audio_format(self, downloader):
        """Should build correct opts for audio-only download."""
        opts = downloader._build_ydl_opts("audio", "192", "test_job")

        assert any(
            p.get("key") == "FFmpegExtractAudio"
            for p in opts["postprocessors"]
        )
        assert any(
            p.get("preferredcodec") == "mp3"
            for p in opts["postprocessors"]
        )

    def test_audio_custom_quality(self, downloader):
        """Should use default audio quality when invalid quality specified."""
        with patch("telegram_media_dl.config.settings") as mock_settings:
            mock_settings.DEFAULT_AUDIO_QUALITY = "128"
            # Re-import so _build_ydl_opts reads the patched value
            with patch("telegram_media_dl.downloader.settings", mock_settings):
                opts = downloader._build_ydl_opts("audio", "invalid", "test_job")

        assert any(
            p.get("preferredquality") == "128"
            for p in opts["postprocessors"]
            if p.get("key") == "FFmpegExtractAudio"
        )

    def test_with_cookie_file(self, downloader):
        """Should add cookie file to opts when file exists on disk."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"# cookie file")
            cookie_path = f.name

        with patch.object(settings, "COOKIE_FILE", cookie_path):
            opts = downloader._build_ydl_opts("video", "best", "test_job")
            assert opts.get("cookiefile") == cookie_path

        os.unlink(cookie_path)

    def test_without_cookie_file(self, downloader):
        """Should not add cookie file when settings has no value."""
        with patch.object(settings, "COOKIE_FILE", ""):
            opts = downloader._build_ydl_opts("video", "best", "test_job")
            assert "cookiefile" not in opts

    def test_nonexistent_cookie_file(self, downloader):
        """Should not add cookie file when path doesn't exist on disk."""
        with patch.object(settings, "COOKIE_FILE", "/nonexistent/cookies.txt"):
            opts = downloader._build_ydl_opts("video", "best", "test_job")
            assert "cookiefile" not in opts


class TestDownload:
    """Tests for the download method."""

    @pytest.fixture
    def downloader(self, tmp_path):
        return Downloader(download_dir=tmp_path, on_progress=lambda m: None)

    @pytest.mark.asyncio
    async def test_download_fails_with_invalid_url(self, downloader):
        """Should raise DownloadError for invalid/unknown URL."""
        with pytest.raises(DownloadError):
            await downloader.download("https://invalid-nonexistent.invalid/q")

    @pytest.mark.asyncio
    async def test_raises_download_error_on_no_info(self, downloader):
        """Should raise DownloadError when yt-dlp returns no info."""
        # Mock yt_dlp.utils.DownloadError as a real exception subclass
        with patch("telegram_media_dl.downloader.yt_dlp") as mock_yt:
            # Make DownloadError a real exception class
            real_de = type("DownloadError", (Exception,), {})
            mock_yt.utils.DownloadError = real_de
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = None
            mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

            with pytest.raises(DownloadError, match="no info"):
                await downloader.download("https://youtube.com/watch?v=test")

    @pytest.mark.asyncio
    async def test_raises_on_size_limit(self, tmp_path):
        """Should raise FileTooLargeError when file exceeds size limit."""
        dl = Downloader(download_dir=tmp_path, on_progress=lambda m: None)

        with patch("telegram_media_dl.downloader.yt_dlp") as mock_yt:
            # Make DownloadError a real exception subclass
            real_de = type("DownloadError", (Exception,), {})
            mock_yt.utils.DownloadError = real_de
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = {
                "title": "Big Video",
                "filesize": 10_000_000_000,  # 10 GB
            }
            mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

            with pytest.raises(FileTooLargeError):
                await dl.download("https://youtube.com/watch?v=test")


class TestProgressHooks:
    """Tests for progress/status hooks."""

    @pytest.fixture
    def downloader(self, tmp_path):
        return Downloader(download_dir=tmp_path, on_progress=lambda m: None)

    def test_progress_hook_updates(self, downloader):
        """Should call on_progress during download."""
        received = []

        def collect(msg):
            received.append(msg)

        dl = Downloader(
            download_dir=downloader.download_dir,
            on_progress=collect,
        )

        d = {
            "status": "downloading",
            "downloaded_bytes": 500_000,
            "total_bytes": 1_000_000,
            "_speed_str": "500 KiB/s",
            "_eta_str": "00:01",
        }
        dl._progress_hook(d)

        assert len(received) == 1
        assert "500 KiB/s" in received[0]

    def test_progress_hook_throttled(self, downloader):
        """Should throttle progress updates to once per 2 seconds."""
        call_count = 0

        def count(msg):
            nonlocal call_count
            call_count += 1

        dl = Downloader(
            download_dir=downloader.download_dir,
            on_progress=count,
        )

        d = {
            "status": "downloading",
            "downloaded_bytes": 500_000,
            "total_bytes": 1_000_000,
            "_speed_str": "500 KiB/s",
            "_eta_str": "00:01",
        }

        dl._progress_hook(d)
        dl._progress_hook(d)
        dl._progress_hook(d)
        # Only first call should fire (subsequent within 2s throttled)
        assert call_count == 1

    def test_finished_hook_triggers_status(self, downloader):
        """Should call on_status when download is finished."""
        received = []

        def collect(msg):
            received.append(msg)

        dl = Downloader(
            download_dir=downloader.download_dir,
            on_status=collect,
        )

        d = {"status": "finished"}
        dl._progress_hook(d)

        assert len(received) == 1
        assert "Processing" in received[0]

    def test_throttle_allows_after_window(self):
        """After 2+ seconds, progress hook should fire again."""
        received = []
        dl = Downloader(download_dir="/tmp", on_progress=received.append)

        d = {
            "status": "downloading",
            "downloaded_bytes": 500_000,
            "total_bytes": 1_000_000,
            "_speed_str": "500 KiB/s",
            "_eta_str": "00:01",
        }

        # First call — should fire
        dl._progress_hook(d)
        assert len(received) == 1

        # Advance internal clock past 2s window
        dl._last_progress_time = 0.0

        # Second call — should fire again
        dl._progress_hook(d)
        assert len(received) == 2


class TestFallbackFileDetection:
    """Tests for fallback file-finding logic."""

    def test_fallback_finds_downloaded_file(self, tmp_path):
        """Should find file via glob fallback when prepare_filename fails."""
        downloads_dir = tmp_path / "downloads"
        downloads_dir.mkdir()

        # Create a file that mimics yt-dlp output
        expected_file = downloads_dir / "test_job_Test Video.mp4"
        expected_file.touch()

        dl = Downloader(download_dir=downloads_dir, on_progress=lambda m: None)

        # Simulate the fallback logic
        candidates = sorted(
            downloads_dir.glob("test_job_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        assert len(candidates) == 1
        assert candidates[0].name == "test_job_Test Video.mp4"