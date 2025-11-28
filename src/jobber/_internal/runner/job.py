# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Generic, TypeVar

from jobber._internal.common.constants import EMPTY, JobStatus
from jobber._internal.exceptions import (
    JobFailedError,
    JobNotCompletedError,
    JobSkippedError,
)

if TYPE_CHECKING:
    from datetime import datetime

ASYNC_FUNC_IGNORED_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""

_ReturnType = TypeVar("_ReturnType")


class Job(Generic[_ReturnType]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_exception",
        "_job_registry",
        "_result",
        "_timer_handler",
        "cron_expression",
        "exec_at",
        "id",
        "job_name",
        "status",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        job_id: str,
        exec_at: datetime,
        job_name: str,
        job_registry: dict[str, Job[_ReturnType]],
        job_status: JobStatus,
        cron_expression: str | None,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._job_registry: dict[str, Job[_ReturnType]] = job_registry
        self._result: _ReturnType = EMPTY
        self._exception: Exception = EMPTY
        self._timer_handler: asyncio.TimerHandle = EMPTY
        self.cron_expression: str | None = cron_expression
        self.exec_at: datetime = exec_at
        self.job_name: str = job_name
        self.status: JobStatus = job_status
        self.id: str = job_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}("
            f"instance_id={id(self)}, "
            f"exec_at={self.exec_at.isoformat()}, "
            f"job_name={self.job_name}, job_id={self.id})"
        )

    def result(self) -> _ReturnType:
        if self.status is JobStatus.SKIPPED:
            raise JobSkippedError
        if self.status is JobStatus.SUCCESS or self._result is not EMPTY:
            return self._result
        if self.status is JobStatus.FAILED:
            raise JobFailedError(
                self.id,
                reason=str(self._exception),
            ) from self._exception
        raise JobNotCompletedError

    def set_result(self, val: _ReturnType) -> None:
        self._result = val

    def set_exception(self, exc: Exception) -> None:
        self._exception = exc

    def _update(
        self,
        *,
        exec_at: datetime,
        job_status: JobStatus,
        time_handler: asyncio.TimerHandle,
    ) -> None:
        self._timer_handler = time_handler
        self.exec_at = exec_at
        self.status = job_status
        self._event = asyncio.Event()

    def is_done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        """Wait until the job is done.

        If the job is already completed, this method returns immediately.
        Safe for concurrent use by multiple coroutines.
        """
        _ = await self._event.wait()

    async def cancel(self) -> None:
        _ = self._job_registry.pop(self.id, None)
        self.status = JobStatus.CANCELED
        self._timer_handler.cancel()
        self._event.set()
