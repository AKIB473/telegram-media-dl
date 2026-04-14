"""YouTube / site search via yt-dlp for telegram-media-dl."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

import yt_dlp

logger = logging.getLogger(__name__)


async def search_videos(
    query: str,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search YouTube via yt-dlp's ytsearch extractor.

    Returns a list of dicts with keys:
    ``title``, ``url``, ``duration``, ``view_count``, ``thumbnail``.
    """
    loop = asyncio.get_event_loop()

    def _run() -> List[Dict[str, Any]]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
        search_query = f"ytsearch{max_results}:{query}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_query, download=False) or {}
        entries = result.get("entries") or []
        items: List[Dict[str, Any]] = []
        for entry in entries:
            if not entry:
                continue
            url = entry.get("url") or entry.get("webpage_url") or ""
            if not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={entry.get('id', '')}"
            items.append(
                {
                    "title": entry.get("title", "Unknown"),
                    "url": url,
                    "duration": entry.get("duration"),
                    "view_count": entry.get("view_count"),
                    "thumbnail": entry.get("thumbnail"),
                }
            )
        return items

    try:
        return await loop.run_in_executor(None, _run)
    except Exception as exc:
        logger.error("Search failed for query %r: %s", query, exc)
        return []
