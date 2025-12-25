from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Generic, TypeVar, final

from typing_extensions import override

from jobber._internal.common.constants import EMPTY, JobStatus
from jobber._internal.exceptions import JobFailedError, JobNotCompletedError

if TYPE_CHECKING:
    from datetime import datetime

    from jobber._internal.storage.abc import Storage

ReturnT = TypeVar("ReturnT")


@final
class Job(Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_handle",
        "_pending_jobs",
        "_result",
        "_status",
        "_storage",
        "cron_expression",
        "exception",
        "exec_at",
        "id",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        job_id: str,
        exec_at: datetime,
        pending_jobs: dict[str, Job[ReturnT]],
        job_status: JobStatus = JobStatus.SCHEDULED,
        storage: Storage,
        cron_expression: str | None = None,
    ) -> None:
        self._event = asyncio.Event()
        self._pending_jobs = pending_jobs
        self._result: ReturnT = EMPTY
        self._status = job_status
        self._storage = storage
        self._handle: asyncio.Handle = EMPTY
        self.id = job_id
        self.exception: Exception | None = None
        self.cron_expression = cron_expression
        self.exec_at = exec_at

    @property
    def status(self) -> JobStatus:
        return self._status

    @override
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}("
            f"instance_id={id(self)}, "
            f"exec_at={self.exec_at.isoformat()}"
        )

    def bind_handle(self, handle: asyncio.Handle) -> None:
        self._handle = handle

    def result(self) -> ReturnT:
        if self.status is JobStatus.SUCCESS or self._result is not EMPTY:
            return self._result
        if self.status is JobStatus.FAILED:
            raise JobFailedError(
                self.id,
                reason=str(self.exception),
            ) from self.exception
        raise JobNotCompletedError

    def set_result(self, val: ReturnT, *, status: JobStatus) -> None:
        self._result = val
        self._status = status

    def set_exception(self, exc: Exception, *, status: JobStatus) -> None:
        self.exception = exc
        self._status = status

    def update(
        self,
        *,
        exec_at: datetime,
        job_status: JobStatus,
        time_handler: asyncio.TimerHandle,
    ) -> None:
        self._status = job_status
        self._event = asyncio.Event()
        self._handle = time_handler
        self.exec_at = exec_at

    def is_done(self) -> bool:
        return self._event.is_set()

    def is_reschedulable(self) -> bool:
        return self._status not in (
            JobStatus.PERMANENTLY_FAILED,
            JobStatus.CANCELLED,
        )

    async def wait(self) -> None:
        """Wait until the job is done.

        If the job is already completed, this method returns immediately.
        Safe for concurrent use by multiple coroutines.
        """
        _ = await self._event.wait()

    async def cancel(self) -> None:
        self._status = JobStatus.CANCELLED
        self._cancel()
        await self._storage.delete_schedule(self.id)

    def _cancel(self) -> None:
        _ = self._pending_jobs.pop(self.id, None)
        self._handle.cancel()
        self._event.set()
