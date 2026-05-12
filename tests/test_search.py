"""Tests for telegram_media_dl.search."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram_media_dl.search import search_videos

from telegram_media_dl.config import settings


@pytest.mark.asyncio
async def test_search_returns_list():
    """Search should return a list of result dicts."""
    mock_entries = [
        {
            "title": "Video 1",
            "url": "https://www.youtube.com/watch?v=abc1",
            "id": "abc1",
            "duration": 120,
            "view_count": 1000,
            "thumbnail": "http://thumb1.jpg",
        },
        {
            "title": "Video 2",
            "id": "abc2",
            "duration": 300,
            "view_count": 5000,
            "webpage_url": "https://www.youtube.com/watch?v=abc2",
        },
    ]

    with patch("telegram_media_dl.search.yt_dlp") as mock_yt:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {"entries": mock_entries}
        mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

        results = await search_videos("test query")

    assert len(results) == 2
    assert results[0]["title"] == "Video 1"
    assert results[1]["title"] == "Video 2"


@pytest.mark.asyncio
async def test_search_returns_empty_on_failure():
    """Search should return empty list when yt-dlp fails."""
    with patch("telegram_media_dl.search.yt_dlp") as mock_yt:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = None
        mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

        results = await search_videos("bad query")

    assert results == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_exception():
    """Search should return empty list when exception occurs."""
    with patch("telegram_media_dl.search.yt_dlp") as mock_yt:
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = Exception("API error")
        mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

        results = await search_videos("test")

    assert results == []


@pytest.mark.asyncio
async def test_search_builds_correct_url_without_url_field():
    """When entry lacks 'url', should construct from 'id'."""
    mock_entries = [
        {
            "title": "No URL Video",
            "id": "xyz99",
            "duration": 60,
            "view_count": 10,
        },
    ]

    with patch("telegram_media_dl.search.yt_dlp") as mock_yt:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {"entries": mock_entries}
        mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

        results = await search_videos("test")

    assert len(results) == 1
    assert "xyz99" in results[0]["url"]
    assert results[0]["url"].startswith("https://www.youtube.com/")


@pytest.mark.asyncio
async def test_search_max_results_limit():
    """Search query should limit to max_results entries."""
    # Create 10 mock entries
    mock_entries = [
        {"title": f"Video {i}", "id": f"id_{i}", "webpage_url": f"https://youtube.com/watch?v={i}"}
        for i in range(10)
    ]

    def _mock_extract_info(search_query, **kwargs):
        """Respect ytsearch{N}: prefix like the real yt-dlp would."""
        # Extract max_results from the query string
        if search_query.startswith("ytsearch"):
            try:
                colon_idx = search_query.index(":")
                limit = int(search_query[len("ytsearch"):colon_idx])
                entries = mock_entries[:limit]
            except (ValueError, IndexError):
                entries = mock_entries
        else:
            entries = mock_entries
        return {"entries": entries}

    with patch("telegram_media_dl.search.yt_dlp") as mock_yt:
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = _mock_extract_info
        mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

        results = await search_videos("test", max_results=3)

    assert len(results) <= 3


@pytest.mark.asyncio
async def test_search_url_starts_with_http():
    """All returned URLs should start with http."""
    mock_entries = [
        {"title": "Test", "id": "abc123", "webpage_url": "https://www.youtube.com/watch?v=abc123"},
    ]

    with patch("telegram_media_dl.search.yt_dlp") as mock_yt:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {"entries": mock_entries}
        mock_yt.YoutubeDL.return_value.__enter__.return_value = mock_instance

        results = await search_videos("test")

    for r in results:
        assert r["url"].startswith("http")