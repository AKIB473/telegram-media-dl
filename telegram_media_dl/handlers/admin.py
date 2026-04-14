"""Admin command handlers: /stats /broadcast /queue /reset."""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from ..config import settings
from ..database import get_all_user_ids, get_stats
from ..queue_manager import DownloadQueue
from ..rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = Router()

_queue: Optional[DownloadQueue] = None
_rate_limiter: Optional[RateLimiter] = None


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    assert message.from_user is not None
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Admin only.")
        return

    db_stats = await get_stats()
    q_stats = _queue.stats() if _queue else {}

    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total users: <b>{db_stats.get('total_users', 0)}</b>\n"
        f"⬇️ Total downloads: <b>{db_stats.get('total_downloads', 0)}</b>\n"
        f"📅 Today's downloads: <b>{db_stats.get('today_downloads', 0)}</b>\n"
    )
    if q_stats:
        text += (
            "\n🗂 <b>Queue</b>\n"
            f"  Queued: {q_stats.get('queued', 0)}\n"
            f"  Active: {q_stats.get('active', 0)}\n"
            f"  Done: {q_stats.get('done', 0)}\n"
            f"  Failed: {q_stats.get('failed', 0)}\n"
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    assert message.from_user is not None and message.text is not None
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Admin only.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /broadcast <message>")
        return

    text = parts[1].strip()
    user_ids = await get_all_user_ids()
    if not user_ids:
        await message.answer("No users found.")
        return

    bot = message.bot
    assert bot is not None

    status = await message.answer(f"📣 Broadcasting to {len(user_ids)} users…")
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, f"📢 {text}")
            sent += 1
        except Exception:
            failed += 1

    await status.edit_text(
        f"✅ Broadcast complete: {sent} delivered, {failed} failed."
    )


@router.message(Command("queue"))
async def cmd_queue(message: Message) -> None:
    assert message.from_user is not None
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Admin only.")
        return

    if not _queue:
        await message.answer("Queue not available.")
        return

    active = _queue.get_active_jobs()
    if not active:
        await message.answer("📭 Queue is empty.")
        return

    lines = ["🗂 <b>Active Queue</b>\n"]
    for job in active:
        lines.append(
            f"• <code>{job.job_id}</code> — user {job.user_id}\n"
            f"  {job.status} | {job.quality} | {job.format_choice}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    assert message.from_user is not None and message.text is not None
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Admin only.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /reset <user_id>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid user ID.")
        return

    if _rate_limiter:
        _rate_limiter.reset(target_id)
        await message.answer(f"✅ Rate limit reset for user {target_id}.")
    else:
        await message.answer("Rate limiter not available.")


def register(
    dp: Dispatcher,
    queue: Optional[DownloadQueue] = None,
    rate_limiter: Optional[RateLimiter] = None,
) -> None:
    global _queue, _rate_limiter
    _queue = queue
    _rate_limiter = rate_limiter
    dp.include_router(router)
