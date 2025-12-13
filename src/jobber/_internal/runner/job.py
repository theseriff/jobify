from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Generic, TypeVar, final

from jobber._internal.common.constants import EMPTY, JobStatus
from jobber._internal.exceptions import JobFailedError, JobNotCompletedError

if TYPE_CHECKING:
    from datetime import datetime

ASYNC_FUNC_IGNORED_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""

ReturnT = TypeVar("ReturnT")


@final
class Job(Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "_cron_failures",
        "_event",
        "_jobs_registry",
        "_result",
        "_timer_handler",
        "cron_expression",
        "exception",
        "exec_at",
        "id",
        "name",
        "status",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        job_id: str,
        exec_at: datetime,
        func_name: str,
        job_registry: dict[str, Job[ReturnT]],
        job_status: JobStatus,
        cron_expression: str | None,
    ) -> None:
        self._event = asyncio.Event()
        self._jobs_registry = job_registry
        self._cron_failures = 0
        self._result: ReturnT = EMPTY
        self._timer_handler: asyncio.TimerHandle = EMPTY
        self.id = job_id
        self.exception: Exception | None = None
        self.cron_expression = cron_expression
        self.exec_at = exec_at
        self.name = func_name
        self.status = job_status

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}("
            f"instance_id={id(self)}, "
            f"exec_at={self.exec_at.isoformat()}, "
            f"job_name={self.name}, job_id={self.id})"
        )

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
        self.status = status

    def set_exception(self, exc: Exception, *, status: JobStatus) -> None:
        self.exception = exc
        self.status = status

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

    def is_cron(self) -> bool:
        return self.cron_expression is not None

    async def wait(self) -> None:
        """Wait until the job is done.

        If the job is already completed, this method returns immediately.
        Safe for concurrent use by multiple coroutines.
        """
        _ = await self._event.wait()

    async def cancel(self) -> None:
        _ = self._jobs_registry.pop(self.id, None)
        self.status = JobStatus.CANCELLED
        self._timer_handler.cancel()
        self._event.set()

    def register_failures(self) -> None:
        self._cron_failures += 1

    def register_success(self) -> None:
        self._cron_failures = 0

    def should_reschedule(self, max_failures: int) -> bool:
        return self._cron_failures < max_failures
