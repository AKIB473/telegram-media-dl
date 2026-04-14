"""Database layer for telegram-media-dl using aiosqlite."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from .config import settings

logger = logging.getLogger(__name__)

_db_path = str(settings.DB_PATH)


async def init_db(db_path: Optional[str] = None) -> None:
    """Create tables if they don't exist."""
    path = db_path or _db_path
    async with aiosqlite.connect(path) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY,
                username      TEXT,
                first_name    TEXT,
                joined_at     TEXT NOT NULL,
                total_downloads INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS downloads (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                url        TEXT NOT NULL,
                title      TEXT,
                format     TEXT,
                quality    TEXT,
                file_size  INTEGER,
                status     TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_prefs (
                user_id         INTEGER PRIMARY KEY,
                default_quality TEXT DEFAULT 'best',
                default_format  TEXT DEFAULT 'video',
                target_chat     TEXT,
                notify_complete INTEGER DEFAULT 1
            );
            """
        )
        await db.commit()
    logger.info("Database initialised at %s", path)


async def register_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    db_path: Optional[str] = None,
) -> None:
    """Insert or update a user record."""
    path = db_path or _db_path
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO users (id, username, first_name, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name, now),
        )
        await db.commit()


async def log_download(
    user_id: int,
    url: str,
    title: Optional[str],
    fmt: Optional[str],
    quality: Optional[str],
    size: Optional[int],
    status: str,
    db_path: Optional[str] = None,
) -> None:
    """Record a download event and increment user counter on success."""
    path = db_path or _db_path
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO downloads (user_id, url, title, format, quality, file_size, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, url, title, fmt, quality, size, status, now),
        )
        if status == "done":
            await db.execute(
                "UPDATE users SET total_downloads = total_downloads + 1 WHERE id = ?",
                (user_id,),
            )
        await db.commit()


async def get_user_history(
    user_id: int,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return last *limit* download records for a user."""
    path = db_path or _db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT title, url, format, quality, file_size, status, created_at
            FROM downloads
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_user_prefs(
    user_id: int,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Return preference dict for user, creating defaults if missing."""
    path = db_path or _db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_prefs WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return dict(row)
    return {
        "user_id": user_id,
        "default_quality": "best",
        "default_format": "video",
        "target_chat": None,
        "notify_complete": 1,
    }


async def set_user_pref(
    user_id: int,
    key: str,
    value: Any,
    db_path: Optional[str] = None,
) -> None:
    """Upsert a single preference value."""
    path = db_path or _db_path
    allowed = {"default_quality", "default_format", "target_chat", "notify_complete"}
    if key not in allowed:
        raise ValueError(f"Unknown preference key: {key}")
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO user_prefs (user_id, default_quality, default_format, target_chat, notify_complete)
            VALUES (?, 'best', 'video', NULL, 1)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id,),
        )
        await db.execute(
            f"UPDATE user_prefs SET {key} = ? WHERE user_id = ?",
            (value, user_id),
        )
        await db.commit()


async def get_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return aggregate statistics."""
    path = db_path or _db_path
    today = datetime.now(timezone.utc).date().isoformat()
    async with aiosqlite.connect(path) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM downloads") as cur:
            total_downloads = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM downloads WHERE created_at LIKE ?", (f"{today}%",)
        ) as cur:
            today_downloads = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "total_downloads": total_downloads,
        "today_downloads": today_downloads,
    }


async def get_all_user_ids(db_path: Optional[str] = None) -> List[int]:
    """Return list of all user IDs (for broadcast)."""
    path = db_path or _db_path
    async with aiosqlite.connect(path) as db:
        async with db.execute("SELECT id FROM users") as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]
