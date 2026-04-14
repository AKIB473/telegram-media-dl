"""URL handler and quality-selection callback for telegram-media-dl."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from ..config import settings
from ..database import log_download
from ..downloader import Downloader, DownloadError
from ..keyboards import quality_keyboard, search_results_keyboard
from ..queue_manager import DownloadJob, DownloadQueue
from ..utils import build_info_message, format_size, is_generic_url, is_valid_url

logger = logging.getLogger(__name__)

router = Router()

# Simple in-memory caches
try:
    from cachetools import TTLCache

    _info_cache: Any = TTLCache(maxsize=256, ttl=300)  # 5 min
except ImportError:
    _info_cache = {}

# Per-user search results store (ephemeral)
_search_cache: Dict[int, List[dict]] = {}

# Per-user "pending download info" store
_pending: Dict[int, Dict[str, Any]] = {}

# Will be injected
_queue: Optional[DownloadQueue] = None
_bot: Optional[Bot] = None


def store_search_results(user_id: int, results: List[dict]) -> None:
    _search_cache[user_id] = results


# ──────────────────────────────────────────────────────────────
# URL message handler
# ──────────────────────────────────────────────────────────────


@router.message(F.text.regexp(r"https?://"))
async def handle_url(message: Message) -> None:
    assert message.text is not None and message.from_user is not None
    url = message.text.strip()

    if not is_generic_url(url):
        return  # silently ignore

    status_msg = await message.answer("🔍 Fetching info…")

    # Check cache
    info = _info_cache.get(url)
    if not info:
        try:
            loop = asyncio.get_event_loop()
            from ..downloader import get_video_info

            info = await loop.run_in_executor(None, get_video_info, url)
            _info_cache[url] = info
        except Exception as exc:
            logger.error("Info fetch failed for %s: %s", url, exc)
            await status_msg.edit_text(f"❌ Could not fetch video info: {exc}")
            return

    # Store pending info for this user
    _pending[message.from_user.id] = {"url": url, "info": info}

    # Show thumbnail + info
    thumbnail = info.get("thumbnail")
    caption = build_info_message(info)
    caption += "\n\n🎛 <b>Select quality:</b>"

    try:
        if thumbnail and settings.SEND_THUMBNAIL:
            await status_msg.delete()
            await message.answer_photo(
                photo=thumbnail,
                caption=caption,
                reply_markup=quality_keyboard(),
                parse_mode="HTML",
            )
        else:
            await status_msg.edit_text(
                caption,
                reply_markup=quality_keyboard(),
                parse_mode="HTML",
            )
    except Exception:
        await status_msg.edit_text(
            caption,
            reply_markup=quality_keyboard(),
            parse_mode="HTML",
        )


# ──────────────────────────────────────────────────────────────
# Quality callback handler
# ──────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("q:"))
async def handle_quality_callback(callback: CallbackQuery) -> None:
    assert callback.from_user is not None and callback.message is not None
    user_id = callback.from_user.id
    data = callback.data or ""

    await callback.answer()

    if data == "q:cancel":
        await callback.message.edit_text("❌ Cancelled.")
        _pending.pop(user_id, None)
        return

    pending = _pending.get(user_id)
    if not pending:
        await callback.message.edit_text("⚠️ Session expired. Please send the URL again.")
        return

    url = pending["url"]

    # Parse quality selection
    # data format: "q:<quality>" or "q:audio:<kbps>"
    parts = data.split(":")
    if len(parts) == 3 and parts[1] == "audio":
        format_choice = "audio"
        quality = parts[2]
    else:
        format_choice = "video"
        quality = parts[1]

    await callback.message.edit_text(
        f"⏳ Download queued: <b>{quality}</b>…",
        parse_mode="HTML",
    )

    if _queue is None:
        await callback.message.edit_text("❌ Download queue not available.")
        return

    progress_message = callback.message

    async def do_download(job: DownloadJob) -> None:
        last_text: Dict[str, str] = {"msg": ""}

        def on_progress(msg: str) -> None:
            last_text["msg"] = msg

        def on_status(msg: str) -> None:
            last_text["msg"] = msg

        downloader = Downloader(
            on_progress=on_progress,
            on_status=on_status,
        )

        # Periodic progress updater
        async def update_progress() -> None:
            while not job.task or not job.task.done():
                if last_text["msg"]:
                    try:
                        await progress_message.edit_text(
                            f"📥 Downloading…\n{last_text['msg']}",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                await asyncio.sleep(3)

        updater = asyncio.create_task(update_progress())

        try:
            filepath, info = await downloader.download(
                url=url,
                format_choice=format_choice,
                quality=quality,
                job_id=job.job_id,
            )
        except DownloadError as exc:
            updater.cancel()
            await progress_message.edit_text(f"❌ Download failed: {exc}")
            await log_download(
                user_id=user_id,
                url=url,
                title=None,
                fmt=format_choice,
                quality=quality,
                size=None,
                status="failed",
            )
            return
        finally:
            updater.cancel()

        updater.cancel()

        # Send file
        size = os.path.getsize(filepath)
        title = info.get("title", "media")
        try:
            await progress_message.edit_text("📤 Uploading…")
            bot = _bot
            if bot is None:
                raise RuntimeError("Bot not available")

            file_input = FSInputFile(filepath)
            chat_id = progress_message.chat.id

            if format_choice == "audio":
                sent = await bot.send_audio(
                    chat_id=chat_id,
                    audio=file_input,
                    title=title,
                    caption=f"🎵 {title}",
                )
            else:
                sent = await bot.send_video(
                    chat_id=chat_id,
                    video=file_input,
                    caption=f"🎬 {title}\n💾 {format_size(size)}",
                    supports_streaming=True,
                )

            # Forward to target chat if configured
            if settings.TARGET_CHAT:
                try:
                    await sent.forward(chat_id=settings.TARGET_CHAT)
                except Exception as fwd_exc:
                    logger.warning("Forward to target chat failed: %s", fwd_exc)

            await progress_message.delete()

            # Log to DB
            await log_download(
                user_id=user_id,
                url=url,
                title=title,
                fmt=format_choice,
                quality=quality,
                size=size,
                status="done",
            )

        except Exception as exc:
            await progress_message.edit_text(f"❌ Upload failed: {exc}")
            logger.error("Upload failed for %s: %s", filepath, exc)
        finally:
            # Clean up downloaded file
            try:
                os.remove(filepath)
            except OSError:
                pass

    _queue.enqueue(
        user_id=user_id,
        url=url,
        format_choice=format_choice,
        quality=quality,
        coro_factory=do_download,
    )
    _pending.pop(user_id, None)


# ──────────────────────────────────────────────────────────────
# Search result callback handler
# ──────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("sr:"))
async def handle_search_callback(callback: CallbackQuery) -> None:
    assert callback.from_user is not None and callback.message is not None
    user_id = callback.from_user.id
    data = callback.data or ""

    await callback.answer()

    if data == "sr:cancel":
        await callback.message.edit_text("❌ Search cancelled.")
        _search_cache.pop(user_id, None)
        return

    idx_str = data.split(":")[1]
    try:
        idx = int(idx_str)
    except ValueError:
        await callback.message.edit_text("❌ Invalid selection.")
        return

    results = _search_cache.get(user_id)
    if not results or idx >= len(results):
        await callback.message.edit_text("⚠️ Search session expired. Please search again.")
        return

    selected = results[idx]
    url = selected.get("url", "")

    # Store as pending and show quality keyboard
    _pending[user_id] = {"url": url, "info": selected}
    _search_cache.pop(user_id, None)

    title = selected.get("title", "Unknown")
    await callback.message.edit_text(
        f"🎬 <b>{title}</b>\n\n🎛 Select quality:",
        reply_markup=quality_keyboard(),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────
# Main menu callback
# ──────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("menu:"))
async def handle_menu(callback: CallbackQuery) -> None:
    assert callback.message is not None
    action = (callback.data or "").split(":")[1]
    await callback.answer()

    if action == "download":
        await callback.message.edit_text(
            "📎 Send me a video/audio URL and I'll download it for you!"
        )
    elif action == "search":
        await callback.message.edit_text(
            "🔍 Use /search <query> to search YouTube."
        )
    elif action == "settings":
        from ..database import get_user_prefs
        from ..keyboards import settings_keyboard

        assert callback.from_user is not None
        prefs = await get_user_prefs(callback.from_user.id)
        await callback.message.edit_text(
            "⚙️ <b>Settings</b>",
            reply_markup=settings_keyboard(prefs),
            parse_mode="HTML",
        )
    elif action == "history":
        from ..database import get_user_history
        from ..utils import format_size

        assert callback.from_user is not None
        history = await get_user_history(callback.from_user.id, limit=10)
        if not history:
            await callback.message.edit_text("📜 No downloads yet.")
            return
        lines = ["📜 <b>Your last downloads:</b>\n"]
        for i, row in enumerate(history, start=1):
            title = row.get("title") or row.get("url", "Unknown")[:60]
            status = row.get("status", "?")
            quality = row.get("quality", "")
            size = row.get("file_size")
            size_str = f" ({format_size(size)})" if size else ""
            lines.append(f"{i}. {title}\n   {quality} • {status}{size_str}")
        await callback.message.edit_text("\n\n".join(lines), parse_mode="HTML")


def register(dp: Dispatcher, queue: DownloadQueue, bot: Optional[Bot] = None) -> None:
    global _queue, _bot
    _queue = queue
    _bot = bot
    dp.include_router(router)
