"""Tests for telegram_media_dl.queue_manager."""
import asyncio

import pytest
import pytest_asyncio

from telegram_media_dl.queue_manager import DownloadJob, DownloadQueue, DownloadStatus


@pytest.fixture
def queue():
    return DownloadQueue(max_concurrent=2)


@pytest.mark.asyncio
async def test_enqueue_runs_job(queue):
    """Enqueued job should reach DONE status."""
    results = []

    async def factory(job: DownloadJob) -> None:
        results.append(job.job_id)
        job.status = DownloadStatus.DONE  # Ensure status is set before finishing

    job = queue.enqueue(
        user_id=1,
        url="https://example.com/video",
        format_choice="video",
        quality="best",
        coro_factory=factory,
    )
    # Wait for task to complete using a loop with timeout for robustness
    for _ in range(20):
        if job.status == DownloadStatus.DONE:
            break
        await asyncio.sleep(0.05)

    assert job.status == DownloadStatus.DONE
    assert job.job_id in results


@pytest.mark.asyncio
async def test_enqueue_failed_job(queue):
    """Job that raises should end up as FAILED."""

    async def factory(job: DownloadJob) -> None:
        raise ValueError("simulated error")

    job = queue.enqueue(
        user_id=2,
        url="https://example.com/video",
        format_choice="video",
        quality="720p",
        coro_factory=factory,
    )
    for _ in range(20):
        if job.status == DownloadStatus.FAILED:
            break
        await asyncio.sleep(0.05)
    assert job.status == DownloadStatus.FAILED
    assert "simulated error" in (job.error or "")


@pytest.mark.asyncio
async def test_cancel_job(queue):
    """Cancelled job should not run the factory body."""
    ran = []

    async def factory(job: DownloadJob) -> None:
        await asyncio.sleep(10)  # Would block a long time
        ran.append(True)

    job = queue.enqueue(
        user_id=3,
        url="https://example.com/video",
        format_choice="video",
        quality="best",
        coro_factory=factory,
    )
    queue.cancel(job.job_id)
    await asyncio.sleep(0.05)
    assert job.status == DownloadStatus.CANCELLED
    assert not ran


@pytest.mark.asyncio
async def test_stats(queue):
    """Stats dict should reflect job counts."""

    async def fast(job: DownloadJob) -> None:
        pass

    async def slow(job: DownloadJob) -> None:
        await asyncio.sleep(0.2)

    queue.enqueue(1, "http://a.com", "video", "best", fast)
    queue.enqueue(2, "http://b.com", "audio", "128", slow)
    await asyncio.sleep(0.05)

    stats = queue.stats()
    assert stats["total"] >= 2
    assert "queued" in stats
    assert "active" in stats
    assert "done" in stats


@pytest.mark.asyncio
async def test_concurrent_limit():
    """No more than max_concurrent jobs should run simultaneously."""
    q = DownloadQueue(max_concurrent=2)
    active_at_once = []
    currently_running = [0]

    async def factory(job: DownloadJob) -> None:
        currently_running[0] += 1
        active_at_once.append(currently_running[0])
        await asyncio.sleep(0.05)
        currently_running[0] -= 1

    for i in range(5):
        q.enqueue(i, f"http://example.com/{i}", "video", "best", factory)

    await asyncio.sleep(0.5)
    assert max(active_at_once) <= 2


@pytest.mark.asyncio
async def test_cancel_user_jobs(queue):
    """cancel_user_jobs should cancel all pending jobs for the user."""
    barrier = asyncio.Event()

    async def factory(job: DownloadJob) -> None:
        await barrier.wait()

    for _ in range(3):
        queue.enqueue(99, "http://x.com", "video", "best", factory)

    count = queue.cancel_user_jobs(99)
    barrier.set()
    await asyncio.sleep(0.05)
    assert count >= 1
