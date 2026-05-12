from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Generic, TypeVar

from typing_extensions import override

from jobify._internal.common.constants import INFINITY, UNSET, JobStatus
from jobify._internal.exceptions import JobFailedError, JobNotCompletedError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from datetime import datetime

    from jobify._internal.configuration import Cron
    from jobify._internal.cron_parser import CronParser
    from jobify._internal.storage.base import Storage

ReturnT = TypeVar("ReturnT")


class CronContext(Generic[ReturnT]):
    """Holds configuration and state for a cron-based job.

    Attributes:
        cron: The cron configuration.
        cron_parser: The parser used to calculate next run times.
        failure_count: Number of consecutive failures.
        job: The associated job instance.
        offset: The base datetime from which the next run is calculated.
        run_count: Number of times this job has been executed.

    """

    __slots__: tuple[str, ...] = (
        "cron",
        "cron_parser",
        "failure_count",
        "job",
        "offset",
        "run_count",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        cron: Cron,
        cron_parser: CronParser,
        failure_count: int = 0,
        job: Job[ReturnT],
        offset: datetime,
        run_count: int,
    ) -> None:
        """Initialize the CronContext.

        Args:
            cron: The cron configuration.
            cron_parser: The parser used to calculate next run times.
            failure_count: Initial failure count.
            job: The associated job instance.
            offset: The base datetime.
            run_count: Initial run count.

        """
        self.cron = cron
        self.cron_parser = cron_parser
        self.failure_count = failure_count
        self.job = job
        self.offset = offset
        self.run_count = run_count

    def is_run_exceeded_by_limit(self) -> bool:
        """Check if the maximum number of runs has been exceeded.

        Returns:
            True if the run limit is reached, False otherwise.

        """
        if self.cron.max_runs == INFINITY:
            return False
        return self.run_count >= self.cron.max_runs

    def is_failure_allowed_by_limit(self) -> bool:
        """Check if the job can still fail based on the allowed limit.

        Returns:
            True if the failure limit has not been reached, False otherwise.

        """
        return self.failure_count < self.cron.max_failures


class Job(Generic[ReturnT]):
    """Represents a scheduled job.

    Attributes:
        id: Unique identifier for the job.
        status: Current status of the job.
        exec_at: The scheduled execution time.
        exception: The exception raised, if any.

    """

    __slots__: tuple[str, ...] = (
        "_cron_context",
        "_event",
        "_handle",
        "_result",
        "_storage",
        "_unregister_hook",
        "exception",
        "exec_at",
        "id",
        "status",
    )

    def __init__(
        self,
        *,
        job_id: str,
        storage: Storage,
        exec_at: datetime,
        unregister_hook: Callable[[str], None],
        job_status: JobStatus = JobStatus.PENDING,
    ) -> None:
        """Initialize the Job.

        Args:
            job_id: Unique identifier for the job.
            storage: Storage backend.
            exec_at: The scheduled execution time.
            unregister_hook: Callback to unregister the job.
            job_status: Initial status of the job.

        """
        self._unregister_hook = unregister_hook
        self._event = asyncio.Event()
        self._result: ReturnT = UNSET
        self._storage = storage
        self._handle: asyncio.Handle | None = None
        self._cron_context: CronContext[ReturnT] | None = None
        self.id = job_id
        self.status = job_status
        self.exception: Exception | None = None
        self.exec_at = exec_at

        self._event.set()

    @property
    def cron_expression(self) -> str | None:
        """Return the cron expression if this is a cron job, else None."""
        if self._cron_context is not None:
            return self._cron_context.cron.expression
        return None

    @override
    def __repr__(self) -> str:
        if self.cron_expression is not None:
            cron_info = f", cron={self.cron_expression!r}"
        else:
            cron_info = ""
        return (
            f"<{type(self).__name__} "
            f"id={self.id!r}, "
            f"status={self.status.value!r}, "
            f"exec_at={self.exec_at.isoformat()!r}"
            f"{cron_info}>"
        )

    def __await__(self) -> Generator[object, None, ReturnT]:
        async def _await() -> ReturnT:
            await self.wait()
            return self.result()

        return _await().__await__()

    def bind_handle(self, handle: asyncio.Handle) -> None:
        """Bind an asyncio handle to the job.

        Args:
            handle: The handle to bind.

        """
        self._handle = handle

    def bind_cron_context(self, ctx: CronContext[ReturnT]) -> None:
        """Bind a cron context to the job.

        Args:
            ctx: The cron context to bind.

        """
        self._cron_context = ctx

    def result(self) -> ReturnT:
        """Return the result of the job.

        Returns:
            The job result.

        Raises:
            JobFailedError: If the job failed.
            JobNotCompletedError: If the job is not yet completed.

        """
        if self.status is JobStatus.SUCCESS or self._result is not UNSET:
            return self._result
        if self.status is JobStatus.FAILED:
            raise JobFailedError(
                self.id,
                reason=str(self.exception),
            ) from self.exception
        raise JobNotCompletedError

    def set_result(self, val: ReturnT, *, status: JobStatus) -> None:
        """Set the result of the job.

        Args:
            val: The job result.
            status: The status to set.

        """
        self._result = val
        self.status = status

    def set_exception(self, exc: Exception, *, status: JobStatus) -> None:
        """Set the exception for the job.

        Args:
            exc: The exception to set.
            status: The status to set.

        """
        self.exception = exc
        self.status = status

    def update(self, *, exec_at: datetime, status: JobStatus) -> None:
        """Update the job schedule and status.

        Args:
            exec_at: The new scheduled time.
            status: The new status.

        """
        self._event = asyncio.Event()
        self.status = status
        self.exec_at = exec_at

    def is_done(self) -> bool:
        """Check if the job is done.

        Returns:
            True if the job is done, False otherwise.

        """
        return self._event.is_set()

    def is_cron(self) -> bool:
        """Check if this is a cron job.

        Returns:
            True if it's a cron job, False otherwise.

        """
        return self._cron_context is not None

    def is_reschedulable(self) -> bool:
        """Check if the job can be rescheduled.

        Returns:
            True if reschedulable, False otherwise.

        """
        return self.status not in (
            JobStatus.PERMANENTLY_FAILED,
            JobStatus.CANCELLED,
        )

    async def wait(self) -> None:
        """Wait until the job is done.

        If the job is already completed, this method returns immediately.
        Safe for concurrent use by multiple coroutines.
        """
        await self._event.wait()

    async def cancel(self) -> None:
        """Cancel the job."""
        self.status = JobStatus.CANCELLED
        self._cancel()
        await self._storage.delete_schedule(self.id)

    def _cancel(self) -> None:
        """Handle cancellation internally."""
        self._event.set()
        self._unregister_hook(self.id)
        if self._handle is not None:
            self._handle.cancel()
