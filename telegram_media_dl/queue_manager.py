"""Async download queue manager for telegram-media-dl."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadJob:
    job_id: str
    user_id: int
    url: str
    format_choice: str
    quality: str
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: str = "0%"
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    task: Optional[asyncio.Task] = field(default=None, repr=False)

    @property
    def elapsed(self) -> Optional[float]:
        if self.started_at:
            end = self.finished_at or time.time()
            return round(end - self.started_at, 1)
        return None


class DownloadQueue:
    """Manages concurrent download jobs with a semaphore."""

    def __init__(self, max_concurrent: int = 3) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._jobs: Dict[str, DownloadJob] = {}
        self._user_jobs: Dict[int, List[str]] = {}
        self._job_counter = 0

    def _new_job_id(self) -> str:
        self._job_counter += 1
        return f"job_{self._job_counter}_{int(time.time())}"

    def enqueue(
        self,
        user_id: int,
        url: str,
        format_choice: str,
        quality: str,
        coro_factory: Callable[[DownloadJob], Coroutine],
    ) -> DownloadJob:
        """Create and schedule a download job."""
        job_id = self._new_job_id()
        job = DownloadJob(
            job_id=job_id,
            user_id=user_id,
            url=url,
            format_choice=format_choice,
            quality=quality,
        )
        self._jobs[job_id] = job
        self._user_jobs.setdefault(user_id, []).append(job_id)

        task = asyncio.create_task(self._run(job, coro_factory))
        job.task = task
        logger.info("Enqueued job %s for user %d", job_id, user_id)
        return job

    async def _run(
        self,
        job: DownloadJob,
        coro_factory: Callable[[DownloadJob], Coroutine],
    ) -> None:
        async with self._semaphore:
            if job.status == DownloadStatus.CANCELLED:
                return
            job.status = DownloadStatus.DOWNLOADING
            job.started_at = time.time()
            try:
                await coro_factory(job)
                job.status = DownloadStatus.DONE
            except asyncio.CancelledError:
                job.status = DownloadStatus.CANCELLED
            except Exception as exc:
                job.status = DownloadStatus.FAILED
                job.error = str(exc)
                logger.error("Job %s failed: %s", job.job_id, exc)
            finally:
                job.finished_at = time.time()

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued or running job. Returns True if found."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = DownloadStatus.CANCELLED
        if job.task and not job.task.done():
            job.task.cancel()
        return True

    def cancel_user_jobs(self, user_id: int) -> int:
        """Cancel all pending/active jobs for *user_id*. Returns count."""
        count = 0
        for job_id in list(self._user_jobs.get(user_id, [])):
            job = self._jobs.get(job_id)
            if job and job.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING):
                if self.cancel(job_id):
                    count += 1
        return count

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        return self._jobs.get(job_id)

    def get_user_jobs(self, user_id: int) -> List[DownloadJob]:
        return [
            self._jobs[jid]
            for jid in self._user_jobs.get(user_id, [])
            if jid in self._jobs
        ]

    def get_active_jobs(self) -> List[DownloadJob]:
        return [
            j
            for j in self._jobs.values()
            if j.status
            in (
                DownloadStatus.QUEUED,
                DownloadStatus.DOWNLOADING,
                DownloadStatus.UPLOADING,
            )
        ]

    def stats(self) -> Dict[str, Any]:
        all_jobs = list(self._jobs.values())
        return {
            "total": len(all_jobs),
            "queued": sum(1 for j in all_jobs if j.status == DownloadStatus.QUEUED),
            "active": sum(
                1 for j in all_jobs if j.status == DownloadStatus.DOWNLOADING
            ),
            "done": sum(1 for j in all_jobs if j.status == DownloadStatus.DONE),
            "failed": sum(1 for j in all_jobs if j.status == DownloadStatus.FAILED),
            "cancelled": sum(
                1 for j in all_jobs if j.status == DownloadStatus.CANCELLED
            ),
            "unique_users": len(self._user_jobs),
        }

    def cleanup_old_jobs(self, max_age_seconds: int = 3600) -> int:
        """Remove finished jobs older than *max_age_seconds*."""
        now = time.time()
        to_remove = [
            jid
            for jid, j in self._jobs.items()
            if j.status
            in (
                DownloadStatus.DONE,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELLED,
            )
            and j.finished_at
            and (now - j.finished_at) > max_age_seconds
        ]
        for jid in to_remove:
            job = self._jobs.pop(jid)
            uid_jobs = self._user_jobs.get(job.user_id, [])
            if jid in uid_jobs:
                uid_jobs.remove(jid)
        return len(to_remove)
