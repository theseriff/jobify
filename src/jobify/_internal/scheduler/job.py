from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar, final

from typing_extensions import override

from jobify._internal.common.constants import EMPTY, INFINITY, JobStatus
from jobify._internal.exceptions import JobFailedError, JobNotCompletedError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from jobify._internal.configuration import Cron
    from jobify._internal.cron_parser import CronParser
    from jobify._internal.storage.abc import Storage

ReturnT = TypeVar("ReturnT")


@dataclass(slots=True, kw_only=True)
class CronContext(Generic[ReturnT]):
    job: Job[ReturnT]
    cron: Cron
    offset: datetime
    cron_parser: CronParser
    run_count: int
    failure_count: int = 0

    def is_run_exceeded_by_limit(self) -> bool:
        if self.cron.max_runs == INFINITY:
            return False
        return self.run_count >= self.cron.max_runs

    def is_failure_allowed_by_limit(self) -> bool:
        return self.failure_count < self.cron.max_failures


@final
class Job(Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "_cron_context",
        "_event",
        "_handle",
        "_result",
        "_status",
        "_storage",
        "_unregister_hook",
        "exception",
        "exec_at",
        "id",
    )

    def __init__(
        self,
        *,
        job_id: str,
        storage: Storage,
        exec_at: datetime,
        unregister_hook: Callable[[str], None],
        job_status: JobStatus = JobStatus.SCHEDULED,
    ) -> None:
        self._unregister_hook = unregister_hook
        self._event = asyncio.Event()
        self._result: ReturnT = EMPTY
        self._status = job_status
        self._storage = storage
        self._handle: asyncio.Handle | None = None
        self._cron_context: CronContext[ReturnT] | None = None
        self.id = job_id
        self.exception: Exception | None = None
        self.exec_at = exec_at

        self._event.set()

    @property
    def cron_expression(self) -> str | None:
        if self._cron_context is not None:
            return self._cron_context.cron.expression
        return None

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

    def bind_cron_context(self, ctx: CronContext[ReturnT]) -> None:
        self._cron_context = ctx

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

    def update(self, *, exec_at: datetime, status: JobStatus) -> None:
        self._status = status
        self._event = asyncio.Event()
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
        self._event.set()
        self._unregister_hook(self.id)
        if self._handle is not None:
            self._handle.cancel()
