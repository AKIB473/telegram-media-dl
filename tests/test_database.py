"""Tests for telegram_media_dl.database using in-memory SQLite."""
from __future__ import annotations

import pytest
import pytest_asyncio

from telegram_media_dl.database import (
    get_stats,
    get_user_history,
    get_user_prefs,
    init_db,
    log_download,
    register_user,
    set_user_pref,
)

# Use a shared in-memory path — aiosqlite uses file paths; ":memory:" is
# per-connection, so we use a temp file created by pytest's tmp_path fixture.


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.mark.asyncio
async def test_init_db(db_path):
    """init_db should run without error and create tables."""
    await init_db(db_path=db_path)  # Should not raise


@pytest.mark.asyncio
async def test_register_user(db_path):
    await init_db(db_path=db_path)
    await register_user(1001, "alice", "Alice", db_path=db_path)

    # Registering again should update (not raise)
    await register_user(1001, "alice_new", "Alice Updated", db_path=db_path)


@pytest.mark.asyncio
async def test_log_download_and_get_history(db_path):
    await init_db(db_path=db_path)
    await register_user(2001, "bob", "Bob", db_path=db_path)

    await log_download(
        user_id=2001,
        url="https://youtube.com/watch?v=abc",
        title="Test Video",
        fmt="video",
        quality="720p",
        size=50_000_000,
        status="done",
        db_path=db_path,
    )

    history = await get_user_history(2001, limit=10, db_path=db_path)
    assert len(history) == 1
    assert history[0]["title"] == "Test Video"
    assert history[0]["status"] == "done"
    assert history[0]["quality"] == "720p"


@pytest.mark.asyncio
async def test_history_limit(db_path):
    await init_db(db_path=db_path)
    await register_user(3001, "carol", "Carol", db_path=db_path)

    for i in range(15):
        await log_download(
            user_id=3001,
            url=f"https://youtube.com/watch?v={i}",
            title=f"Video {i}",
            fmt="video",
            quality="best",
            size=None,
            status="done",
            db_path=db_path,
        )

    history = await get_user_history(3001, limit=10, db_path=db_path)
    assert len(history) == 10


@pytest.mark.asyncio
async def test_get_user_prefs_defaults(db_path):
    await init_db(db_path=db_path)
    prefs = await get_user_prefs(9999, db_path=db_path)
    assert prefs["default_quality"] == "best"
    assert prefs["default_format"] == "video"
    assert prefs["notify_complete"] == 1


@pytest.mark.asyncio
async def test_set_user_pref(db_path):
    await init_db(db_path=db_path)
    await register_user(4001, "dave", "Dave", db_path=db_path)

    await set_user_pref(4001, "default_quality", "720p", db_path=db_path)
    prefs = await get_user_prefs(4001, db_path=db_path)
    assert prefs["default_quality"] == "720p"


@pytest.mark.asyncio
async def test_set_user_pref_notify(db_path):
    await init_db(db_path=db_path)
    await register_user(5001, "eve", "Eve", db_path=db_path)

    await set_user_pref(5001, "notify_complete", 0, db_path=db_path)
    prefs = await get_user_prefs(5001, db_path=db_path)
    assert prefs["notify_complete"] == 0


@pytest.mark.asyncio
async def test_set_invalid_pref(db_path):
    await init_db(db_path=db_path)
    with pytest.raises(ValueError, match="Unknown preference key"):
        await set_user_pref(1, "nonexistent_key", "value", db_path=db_path)


@pytest.mark.asyncio
async def test_get_stats(db_path):
    await init_db(db_path=db_path)
    await register_user(6001, "frank", "Frank", db_path=db_path)
    await register_user(6002, "grace", "Grace", db_path=db_path)

    await log_download(
        user_id=6001,
        url="https://youtube.com/watch?v=x",
        title="vid",
        fmt="video",
        quality="best",
        size=None,
        status="done",
        db_path=db_path,
    )

    stats = await get_stats(db_path=db_path)
    assert stats["total_users"] == 2
    assert stats["total_downloads"] == 1
    assert stats["today_downloads"] == 1
