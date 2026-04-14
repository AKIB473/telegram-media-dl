"""Command handlers: /start /help /search /history /settings /cancel."""
from __future__ import annotations

import logging

from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from ..database import get_user_history, get_user_prefs
from ..keyboards import main_menu_keyboard, search_results_keyboard, settings_keyboard
from ..queue_manager import DownloadQueue
from ..search import search_videos
from ..utils import format_duration, format_size

logger = logging.getLogger(__name__)

router = Router()

# Will be set during register()
_queue: DownloadQueue | None = None

WELCOME_TEXT = (
    "👋 Welcome to <b>Telegram Media Downloader</b>!\n\n"
    "Send me any video/audio URL (YouTube, Instagram, TikTok, Twitter…) "
    "and I'll download it for you.\n\n"
    "Use the buttons below to get started:"
)

HELP_TEXT = (
    "📖 <b>Help</b>\n\n"
    "<b>Supported sites:</b>\n"
    "YouTube, Instagram, TikTok, Twitter/X, Facebook, Reddit, Twitch, "
    "Vimeo, SoundCloud, Bandcamp and many more.\n\n"
    "<b>Commands:</b>\n"
    "/start — welcome screen\n"
    "/help — this message\n"
    "/search &lt;query&gt; — search YouTube\n"
    "/history — last 10 downloads\n"
    "/settings — preferences\n"
    "/cancel — cancel active downloads\n\n"
    "<b>Admin only:</b>\n"
    "/stats — bot statistics\n"
    "/broadcast &lt;msg&gt; — message all users\n"
    "/queue — show active queue\n"
    "/reset &lt;user_id&gt; — reset rate limit\n"
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    assert message.text is not None
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /search <query>")
        return

    query = parts[1].strip()
    if not query:
        await message.answer("Please provide a search query.")
        return

    status_msg = await message.answer("🔍 Searching…")
    results = await search_videos(query)

    if not results:
        await status_msg.edit_text("❌ No results found.")
        return

    # Format results text
    lines = ["🔍 <b>Search Results</b>\n"]
    for i, r in enumerate(results, start=1):
        title = r.get("title", "Unknown")
        dur = format_duration(r.get("duration"))
        views = r.get("view_count")
        views_str = f"{views:,}" if views else "N/A"
        lines.append(f"{i}. <b>{title}</b>\n   ⏱ {dur} | 👁 {views_str}")

    # Store results in a simple in-message callback approach
    # We use the message object to relay results; the callback handler will
    # access them via a shared cache (see downloads.py)
    from ..handlers.downloads import store_search_results

    store_search_results(message.from_user.id, results)  # type: ignore[union-attr]

    await status_msg.edit_text(
        "\n\n".join(lines),
        reply_markup=search_results_keyboard(results),
        parse_mode="HTML",
    )


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    assert message.from_user is not None
    history = await get_user_history(message.from_user.id, limit=10)
    if not history:
        await message.answer("📜 No downloads yet.")
        return

    lines = ["📜 <b>Your last downloads:</b>\n"]
    for i, row in enumerate(history, start=1):
        title = row.get("title") or row.get("url", "Unknown")[:60]
        status = row.get("status", "?")
        quality = row.get("quality", "")
        size = row.get("file_size")
        size_str = f" ({format_size(size)})" if size else ""
        lines.append(f"{i}. {title}\n   {quality} • {status}{size_str}")

    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    assert message.from_user is not None
    prefs = await get_user_prefs(message.from_user.id)
    await message.answer(
        "⚙️ <b>Settings</b>",
        reply_markup=settings_keyboard(prefs),
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    if _queue is None:
        await message.answer("No active downloads.")
        return
    assert message.from_user is not None
    count = _queue.cancel_user_jobs(message.from_user.id)
    if count:
        await message.answer(f"✅ Cancelled {count} download(s).")
    else:
        await message.answer("No active downloads to cancel.")


def register(dp: Dispatcher, queue: DownloadQueue | None = None) -> None:
    global _queue
    _queue = queue
    dp.include_router(router)
