"""Background async sync queue for CMS operations.

Decouples CMS push/pull operations from the intake flow by processing
them asynchronously via an asyncio.Queue. Supports retry with exponential
backoff and graceful error handling.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.integrations.cms.base import CMSAdapter

logger = logging.getLogger(__name__)

# Maximum retry attempts before marking a job as permanently failed
MAX_RETRIES = 3


@dataclass
class SyncJob:
    """A single sync operation to be processed by the queue.

    Attributes:
        adapter: CMS adapter instance to call.
        method: Adapter method name (push_contact, push_matter, etc.).
        args: Keyword arguments to pass to the method.
        retry_count: Number of times this job has been retried.
        error_message: Last error message if the job failed.
    """

    adapter: CMSAdapter
    method: str
    args: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    error_message: str | None = None


class CMSSyncQueue:
    """Async queue for background CMS sync operations.

    Wraps asyncio.Queue to provide enqueue/process semantics with
    retry logic and error handling. Jobs that fail are retried up to
    MAX_RETRIES times with exponential backoff.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[SyncJob] = asyncio.Queue()
        self._failed_jobs: list[SyncJob] = []

    async def enqueue(self, job: SyncJob) -> None:
        """Add a sync job to the processing queue.

        Args:
            job: The sync job to enqueue.
        """
        await self._queue.put(job)
        logger.debug(
            "Enqueued CMS sync job: %s.%s (retry=%d)",
            job.adapter.adapter_name,
            job.method,
            job.retry_count,
        )

    async def process_next(self) -> SyncJob | None:
        """Dequeue and execute the next sync job.

        Returns:
            The processed SyncJob (with updated status), or None if queue is empty.

        Error handling:
            - Logs errors via structlog/logging
            - Does not crash on adapter errors
            - Marks job as failed after MAX_RETRIES
            - Re-enqueues with incremented retry_count if retries remain
        """
        try:
            job = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        try:
            method = getattr(job.adapter, job.method)
            await method(**job.args)
            logger.info(
                "CMS sync job completed: %s.%s",
                job.adapter.adapter_name,
                job.method,
            )
            return job

        except Exception as exc:
            job.retry_count += 1
            job.error_message = str(exc)

            if job.retry_count >= MAX_RETRIES:
                logger.error(
                    "CMS sync job permanently failed after %d retries: %s.%s - %s",
                    MAX_RETRIES,
                    job.adapter.adapter_name,
                    job.method,
                    exc,
                )
                self._failed_jobs.append(job)
            else:
                # Re-enqueue with exponential backoff delay
                backoff = 2 ** job.retry_count
                logger.warning(
                    "CMS sync job failed (retry %d/%d, backoff %ds): %s.%s - %s",
                    job.retry_count,
                    MAX_RETRIES,
                    backoff,
                    job.adapter.adapter_name,
                    job.method,
                    exc,
                )
                await self._queue.put(job)

            return job

    async def run_worker(self, interval_seconds: int = 5) -> None:
        """Background loop that continuously processes sync jobs.

        Runs indefinitely, processing jobs from the queue with a configurable
        polling interval when the queue is empty.

        Args:
            interval_seconds: Seconds to wait between poll cycles when idle.
        """
        logger.info("CMS sync worker started (interval=%ds)", interval_seconds)
        while True:
            if self._queue.empty():
                await asyncio.sleep(interval_seconds)
                continue

            await self.process_next()

    @property
    def pending_count(self) -> int:
        """Number of jobs waiting in the queue."""
        return self._queue.qsize()

    @property
    def failed_jobs(self) -> list[SyncJob]:
        """Jobs that permanently failed after all retries."""
        return list(self._failed_jobs)
