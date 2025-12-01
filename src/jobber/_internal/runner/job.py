# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Generic, TypeVar, final

from jobber._internal.common.constants import EMPTY, JobStatus
from jobber._internal.exceptions import (
    JobFailedError,
    JobNotCompletedError,
    JobSkippedError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

ASYNC_FUNC_IGNORED_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""

_R = TypeVar("_R")


@final
class Job(Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_job_registry",
        "_result",
        "_timer_handler",
        "cron_expression",
        "exception",
        "exec_at",
        "id",
        "job_name",
        "metadata",
        "status",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        job_id: str,
        exec_at: datetime,
        job_name: str,
        job_registry: dict[str, Job[_R]],
        job_status: JobStatus,
        cron_expression: str | None,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        self.id = job_id
        self._event = asyncio.Event()
        self._job_registry = job_registry
        self._result: _R = EMPTY
        self.exception: Exception | None = None
        self._timer_handler: asyncio.TimerHandle = EMPTY
        self.cron_expression = cron_expression
        self.exec_at = exec_at
        self.job_name = job_name
        self.status = job_status
        self.metadata = metadata

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}("
            f"instance_id={id(self)}, "
            f"exec_at={self.exec_at.isoformat()}, "
            f"job_name={self.job_name}, job_id={self.id})"
        )

    def result(self) -> _R:
        if self.status is JobStatus.SKIPPED:
            raise JobSkippedError
        if self.status is JobStatus.SUCCESS or self._result is not EMPTY:
            return self._result
        if self.status is JobStatus.FAILED:
            raise JobFailedError(
                self.id,
                reason=str(self.exception),
            ) from self.exception
        raise JobNotCompletedError

    def set_result(self, val: _R) -> None:
        self._result = val

    def set_exception(self, exc: Exception) -> None:
        self.exception = exc

    def update(
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
        _me = self._job_registry.pop(self.id, None)
        self.status = JobStatus.CANCELLED
        self._timer_handler.cancel()
        self._event.set()
