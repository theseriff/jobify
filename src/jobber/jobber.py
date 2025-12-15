"""Jobber entrypoint."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal, TypeVar
from zoneinfo import ZoneInfo

from jobber._internal.configuration import JobberConfiguration, WorkerPools
from jobber._internal.router.root import RootRouter
from jobber._internal.serializers.json import JSONSerializer
from jobber._internal.storage.dummy import DummyRepository
from jobber._internal.storage.sqlite import SQLiteJobRepository
from jobber.crontab import create_crontab

if TYPE_CHECKING:
    from collections.abc import Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType

    from jobber._internal.common.types import Lifespan, LoopFactory
    from jobber._internal.cron_parser import FactoryCron
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.middleware.exceptions import MappingExceptionHandlers
    from jobber._internal.serializers.base import JobsSerializer
    from jobber._internal.storage.abc import JobRepository


AppT = TypeVar("AppT", bound="Jobber")


class Jobber(RootRouter):
    """Jobber is the main app for scheduling and managing background jobs.

    It provides a flexible and extensible framework for defining, running,
    and persisting jobs, supporting various executors, middleware, and
    serialization options.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo | None = None,
        loop_factory: LoopFactory = lambda: asyncio.get_running_loop(),
        durable: JobRepository | Literal[False] | None = None,
        lifespan: Lifespan[AppT] | None = None,
        serializer: JobsSerializer | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
        exception_handlers: MappingExceptionHandlers | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
        factory_cron: FactoryCron | None = None,
    ) -> None:
        """Initialize a `Jobber` instance."""
        if durable is False:
            durable = DummyRepository()
        elif durable is None:
            durable = SQLiteJobRepository()

        self.jobber_config: JobberConfiguration = JobberConfiguration(
            loop_factory=loop_factory,
            tz=tz or ZoneInfo("UTC"),
            durable=durable,
            worker_pools=WorkerPools(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            serializer=serializer or JSONSerializer(),
            factory_cron=factory_cron or create_crontab,
            _tasks_registry=set(),
            _jobs_registry={},
        )

        super().__init__(
            lifespan=lifespan,
            middleware=middleware,
            jobber_config=self.jobber_config,
            exception_handlers=exception_handlers,
        )

    async def wait_all(self, timeout: float | None = None) -> None:
        """Wait for all currently scheduled jobs to complete.

        This method waits until all jobs currently registered have finished
        executing (with statuses of SUCCESS, FAILED, or TIMEOUT). This is
        useful in situations where it's important to ensure that background
        tasks have completed before moving on.

        The method sets an internal event when both conditions are met:
        1. No jobs remain in the jobs registry (`_jobs_registry`)

        Args:
            timeout (optional): The maximum time in seconds to wait for the
                jobs to complete. If not specified, the default value of `None`
                will be used, which means the job will wait indefinitely. If a
                timeout is specified and it is reached, the method will raise
                an `asyncio.TimeoutError`.

        Example:
            ```python
            # Wait for all scheduled jobs to complete
            await jobber.wait_all()
            print("All jobs completed!")

            # Or with a timeout (raises asyncio.TimeoutError on timeout)
            try:
                await jobber.wait_all(timeout=30.0)
            except asyncio.TimeoutError:
                print("Timeout reached while waiting for jobs")
            ```

        """

        async def target() -> None:
            while jobs := self.jobber_config._jobs_registry.values():
                coros = (job.wait() for job in jobs)
                _ = await asyncio.gather(*coros)

        await asyncio.wait_for(target(), timeout=timeout)

    async def startup(self) -> None:
        """Initialize the Jobber application.

        This method:
        1. Marks the application as started
        2. Propagates startup events to all routers and their registrators
        3. Schedules any pending cron jobs

        Raises:
            RuntimeError: If application startup fails due to configuration
            issues or router initialization errors.

        """
        self.jobber_config.app_started = True
        await self._propagate_startup(self)
        await self.task.start_crons()

    async def shutdown(self) -> None:
        """Gracefully shut down the Jobber application.

        This method performs a structured shutdown:
        1. Marks the application as stopped (`app_started = False`).
        2. Propagates shutdown events to all routers/components.
        3. Cancels all scheduled future jobs in the registry
           (`_jobs_registry`).
        4. Closes the jobber configuration (e.g., stopping the internal
           scheduler).
        5. Cancels all currently running tasks (in `_tasks_registry`), waits
           for their completion, and explicitly clears the task registry.

        Note:
            The method uses `return_exceptions=True` when gathering cancelled
            tasks to prevent shutdown from being interrupted by task exception.

        """
        self.jobber_config.app_started = False
        await self._propagate_shutdown()

        if jobs := tuple(self.jobber_config._jobs_registry.values()):
            for job in jobs:
                job._cancel()

        self.jobber_config.close()

        if tasks := self.jobber_config._tasks_registry:
            for task in tuple(tasks):
                _ = task.cancel()
            _ = await asyncio.gather(*tasks, return_exceptions=True)
            tasks.clear()

    async def __aenter__(self) -> Jobber:
        """Enter the Jobber context manager.

        Returns:
            The initialized Jobber instance ready for use.

        Raises:
            Any exception raised by `startup()` method.

        """
        await self.startup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        """Exit the Jobber context manager.

        Note:
            This method ensures proper shutdown regardless of whether an
            exception occurred in the managed context. The exception parameters
            are ignored as shutdown should proceed even if the context failed.

        """
        await self.shutdown()
