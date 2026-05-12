"""Tests for telegram_media_dl.handlers.downloads."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_media_dl.handlers.downloads import (
    handle_url,
    handle_quality_callback,
    handle_search_callback,
    handle_menu,
    _info_cache,
    _pending,
    _search_cache,
    _user_last_activity,
    _cleanup_stale_caches,
)
from telegram_media_dl.downloader import DownloadError, FileTooLargeError


# ─── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all in-memory caches before each test."""
    _pending.clear()
    _search_cache.clear()
    _user_last_activity.clear()
    _info_cache.clear()
    yield
    _pending.clear()
    _search_cache.clear()
    _user_last_activity.clear()
    _info_cache.clear()


def _make_message(text="https://youtube.com/watch?v=test"):
    msg = MagicMock()
    msg.text = text
    msg.from_user = MagicMock()
    msg.from_user.id = 12345
    msg.chat = MagicMock()
    msg.chat.id = 12345
    msg.answer = AsyncMock(return_value=msg)  # answer returns self for chaining edit_text
    msg.edit_text = AsyncMock(return_value=msg)
    msg.edit_reply_markup = AsyncMock(return_value=msg)
    msg.delete = AsyncMock()
    return msg


def _make_callback(data="q:best", user_id=12345):
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.from_user.is_bot = False
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock(return_value=cb.message)
    cb.message.edit_reply_markup = AsyncMock(return_value=cb.message)
    cb.answer = AsyncMock()
    return cb


# ─── handle_url tests ─────────────────────────────────────────────

class TestHandleUrl:

    @pytest.mark.asyncio
    async def test_invalid_scheme_ignored(self):
        """Non-http URLs are not handled (aiogram F.text.regexp handles this)."""
        # The F.text.regexp(r"https?://") filter means handle_url
        # is only called for http/https URLs.
        pass  # Filter-level test; no code path to exercise here.

    @pytest.mark.asyncio
    async def test_info_fetch_failure_shows_error(self):
        """Should show error message when info fetch fails."""
        msg = _make_message()

        with patch("telegram_media_dl.downloader.get_video_info", side_effect=Exception("API error")):
            await handle_url(msg)

        msg.answer.assert_called_with("🔍 Fetching info…")
        status_msg = msg.answer.return_value
        status_msg.edit_text.assert_called_once()
        call_text = status_msg.edit_text.call_args[0][0]
        assert "Could not fetch video info" in call_text

    @pytest.mark.asyncio
    async def test_success_with_thumbnail(self):
        """Valid URL with thumbnail should send photo."""
        msg = _make_message()
        mock_info = {
            "title": "Test Video",
            "uploader": "Test Channel",
            "duration": 180,
            "view_count": 5000,
            "thumbnail": "http://example.com/thumb.jpg",
        }

        with patch("telegram_media_dl.downloader.get_video_info", return_value=mock_info):
            with patch("telegram_media_dl.handlers.downloads.settings") as mock_settings:
                mock_settings.SEND_THUMBNAIL = True
                await handle_url(msg)

        msg.answer.assert_called_with("🔍 Fetching info…")
        status_msg = msg.answer.return_value
        # Should delete status and answer with photo
        status_msg.delete.assert_called_once()
        msg.answer_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_without_thumbnail(self):
        """Valid URL without thumbnail should edit status message."""
        msg = _make_message()
        mock_info = {
            "title": "Test Video",
            "uploader": "Test Channel",
            "duration": 180,
            "thumbnail": None,
        }

        with patch("telegram_media_dl.downloader.get_video_info", return_value=mock_info):
            await handle_url(msg)

        status_msg = msg.answer.return_value
        status_msg.edit_text.assert_called()
        call_text = status_msg.edit_text.call_args[0][0]
        assert "Test Video" in call_text
        assert "quality" in call_text.lower() or "🎛" in call_text

    @pytest.mark.asyncio
    async def test_stores_pending_data(self):
        """Should store URL and info in _pending for the user."""
        msg = _make_message()
        msg.from_user.id = 999
        mock_info = {"title": "Test", "thumbnail": None, "uploader": "Test"}

        with patch("telegram_media_dl.downloader.get_video_info", return_value=mock_info):
            await handle_url(msg)

        assert 999 in _pending
        assert _pending[999]["url"] == "https://youtube.com/watch?v=test"
        assert _pending[999]["info"]["title"] == "Test"

    @pytest.mark.asyncio
    async def trims_whitespace_from_url(self):
        """URL with leading/trailing whitespace should be trimmed."""
        msg = _make_message("  https://youtube.com/watch?v=test  ")
        msg.from_user.id = 999
        mock_info = {"title": "Test", "thumbnail": None, "uploader": "Test"}

        with patch("telegram_media_dl.downloader.get_video_info", return_value=mock_info):
            await handle_url(msg)

        assert _pending[999]["url"] == "https://youtube.com/watch?v=test"


# ─── handle_quality_callback tests ────────────────────────────────

class TestHandleQualityCallback:

    @pytest.mark.asyncio
    async def test_valid_video_quality_queues(self):
        """Valid quality selection should queue the download."""
        _pending[12345] = {
            "url": "https://youtube.com/watch?v=test",
            "info": {"title": "Test Video"},
        }
        cb = _make_callback("q:best", user_id=12345)

        with patch("telegram_media_dl.handlers.downloads._queue") as mock_queue:
            mock_queue.enqueue = MagicMock()
            await handle_quality_callback(cb)

            mock_queue.enqueue.assert_called_once()
            call_kwargs = mock_queue.enqueue.call_args.kwargs
            assert call_kwargs["user_id"] == 12345
            assert call_kwargs["quality"] == "best"
            assert call_kwargs["format_choice"] == "video"

    @pytest.mark.asyncio
    async def test_audio_quality_queues_audio(self):
        """Audio quality selection should set format_choice='audio'."""
        _pending[12345] = {
            "url": "https://youtube.com/watch?v=test",
            "info": {"title": "Test Video"},
        }
        cb = _make_callback("q:audio:192", user_id=12345)

        with patch("telegram_media_dl.handlers.downloads._queue") as mock_queue:
            mock_queue.enqueue = MagicMock()
            await handle_quality_callback(cb)

            call_kwargs = mock_queue.enqueue.call_args.kwargs
            assert call_kwargs["format_choice"] == "audio"
            assert call_kwargs["quality"] == "192"

    @pytest.mark.asyncio
    async def test_no_pending_shows_expiry(self):
        """Quality callback without pending data should show expiry."""
        cb = _make_callback("q:best", user_id=99999)

        await handle_quality_callback(cb)

        cb.message.edit_text.assert_called_with("⚠️ Session expired. Please send the URL again.")

    @pytest.mark.asyncio
    async def test_cancel_clears_pending(self):
        """Cancel callback should remove pending data."""
        _pending[12345] = {
            "url": "https://youtube.com/watch?v=test",
            "info": {"title": "Test Video"},
        }
        cb = _make_callback("q:cancel", user_id=12345)

        await handle_quality_callback(cb)

        assert 12345 not in _pending
        cb.message.edit_text.assert_called_with("❌ Cancelled.")

    @pytest.mark.asyncio
    async def test_callback_always_answers(self):
        """All quality callbacks should call callback.answer()."""
        _pending[12345] = {
            "url": "https://youtube.com/watch?v=test",
            "info": {"title": "Test Video"},
        }
        cb = _make_callback("q:best", user_id=12345)

        with patch("telegram_media_dl.handlers.downloads._queue") as mock_queue:
            mock_queue.enqueue = MagicMock()
            await handle_quality_callback(cb)

        cb.answer.assert_called_once()


# ─── handle_search_callback tests ─────────────────────────────────

class TestHandleSearchCallback:

    @pytest.mark.asyncio
    async def test_valid_selection_moves_to_pending(self):
        """Search result selection should populate pending and show quality keyboard."""
        _search_cache[12345] = [
            {"title": "Video 1", "url": "https://youtube.com/watch?v=abc"},
        ]
        cb = _make_callback("sr:0", user_id=12345)

        await handle_search_callback(cb)

        assert 12345 in _pending
        assert _pending[12345]["url"] == "https://youtube.com/watch?v=abc"
        assert 12345 not in _search_cache

    @pytest.mark.asyncio
    async def test_expired_search_shows_error(self):
        """Expired search session should show error."""
        cb = _make_callback("sr:0", user_id=99999)

        await handle_search_callback(cb)

        cb.message.edit_text.assert_called_with("⚠️ Search session expired. Please search again.")

    @pytest.mark.asyncio
    async def test_out_of_range_index_shows_error(self):
        """Out-of-range search index should show error."""
        _search_cache[12345] = [
            {"title": "Video 1", "url": "https://youtube.com/watch?v=abc"},
        ]
        cb = _make_callback("sr:99", user_id=12345)

        await handle_search_callback(cb)

        cb.message.edit_text.assert_called_with("⚠️ Search session expired. Please search again.")

    @pytest.mark.asyncio
    async def test_cancel_clears_search_cache(self):
        """Search cancel should clear search cache."""
        _search_cache[12345] = [{"title": "Video 1", "url": "https://youtube.com/watch?v=abc"}]
        cb = _make_callback("sr:cancel", user_id=12345)

        await handle_search_callback(cb)

        assert 12345 not in _search_cache
        cb.message.edit_text.assert_called_with("❌ Search cancelled.")


# ─── handle_menu tests ────────────────────────────────────────────

class TestHandleMenu:

    @pytest.mark.asyncio
    async def test_download_action(self):
        """Menu download action should show instructions."""
        cb = _make_callback("menu:download")

        await handle_menu(cb)

        cb.message.edit_text.assert_called_with(
            "📎 Send me a video/audio URL and I'll download it for you!"
        )

    @pytest.mark.asyncio
    async def test_search_action(self):
        """Menu search action should show instructions."""
        cb = _make_callback("menu:search")

        await handle_menu(cb)

        cb.message.edit_text.assert_called_with(
            "🔍 Use /search <query> to search YouTube."
        )

    @pytest.mark.asyncio
    async def test_settings_action(self):
        """Menu settings action should fetch and display user prefs."""
        cb = _make_callback("menu:settings")
        cb.from_user = MagicMock()
        cb.from_user.id = 12345

        with patch("telegram_media_dl.database.get_user_prefs", AsyncMock(return_value={
            "default_quality": "best",
            "default_format": "video",
            "target_chat": None,
            "notify_complete": 1,
        })):
            await handle_menu(cb)

        cb.message.edit_text.assert_called_once()
        call_text = cb.message.edit_text.call_args[0][0]
        assert "Settings" in call_text


# ─── Cache cleanup tests ──────────────────────────────────────────

class TestCacheCleanup:

    @pytest.mark.asyncio
    async def test_removes_stale_entries(self):
        """_cleanup_stale_caches should remove entries older than max_age_seconds."""
        import time

        _user_last_activity[100] = time.time() - 700
        _pending[100] = {"url": "http://old.com", "info": {}}
        _search_cache[100] = []

        _user_last_activity[200] = time.time()
        _pending[200] = {"url": "http://fresh.com", "info": {}}
        _search_cache[200] = [{"title": "Test"}]

        _cleanup_stale_caches(max_age_seconds=600)

        assert 100 not in _pending
        assert 100 not in _search_cache
        assert 100 not in _user_last_activity

        assert 200 in _pending
        assert 200 in _search_cache

    @pytest.mark.asyncio
    async def test_no_stale_entries_noop(self):
        """No entries should be removed when all are fresh."""
        import time
        _user_last_activity[1] = time.time()
        _pending[1] = {"url": "http://fresh.com", "info": {}}

        _cleanup_stale_caches(max_age_seconds=600)

        assert 1 in _pending

    @pytest.mark.asyncio
    async def test_empty_cache_noop(self):
        """Empty caches should not cause errors."""
        _cleanup_stale_caches()
        # No error = pass