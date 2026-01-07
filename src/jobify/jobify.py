"""Jobify entrypoint."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING, Literal, ParamSpec, TypeVar
from zoneinfo import ZoneInfo

from typing_extensions import Self

from jobify._internal.configuration import (
    Cron,
    JobifyConfiguration,
    WorkerPools,
)
from jobify._internal.message import Message
from jobify._internal.router.root import RootRouter
from jobify._internal.serializers.json import JSONSerializer
from jobify._internal.serializers.json_extended import ExtendedJSONSerializer
from jobify._internal.shared_state import SharedState
from jobify._internal.storage.dummy import DummyStorage
from jobify._internal.storage.sqlite import SQLiteStorage
from jobify._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobify.crontab import create_crontab

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType

    from jobify._internal.common.types import Lifespan, LoopFactory
    from jobify._internal.cron_parser import CronFactory
    from jobify._internal.middleware.base import BaseMiddleware
    from jobify._internal.middleware.exceptions import MappingExceptionHandlers
    from jobify._internal.scheduler.job import Job
    from jobify._internal.serializers.base import Serializer
    from jobify._internal.storage.abc import Storage
    from jobify._internal.typeadapter.base import Dumper, Loader


AppT = TypeVar("AppT", bound="Jobify")
ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")

logger = logging.getLogger("Jobify")


def cache_result(f: Callable[ParamsT, ReturnT]) -> Callable[ParamsT, ReturnT]:
    """Cache the result of the first function call."""
    result: ReturnT | None = None

    @functools.wraps(f)
    def wrapper(*args: ParamsT.args, **kwargs: ParamsT.kwargs) -> ReturnT:
        nonlocal result
        if result is None:
            result = f(*args, **kwargs)
        return result

    return wrapper


class Jobify(RootRouter):
    """Jobify is the main app for scheduling and managing background jobs.

    It provides a flexible and extensible framework for defining, running,
    and persisting jobs, supporting various executors, middleware, and
    serialization options.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo | None = None,
        dumper: Dumper | None = None,
        loader: Loader | None = None,
        storage: Storage | Literal[False] | None = None,
        lifespan: Lifespan[AppT] | None = None,
        serializer: Serializer | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
        cron_factory: CronFactory | None = None,
        loop_factory: LoopFactory = asyncio.get_running_loop,
        exception_handlers: MappingExceptionHandlers | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
    ) -> None:
        """Initialize a `Jobify` instance."""
        getloop = cache_result(loop_factory)

        if storage is False:
            storage = DummyStorage()
        elif storage is None:
            storage = SQLiteStorage()

        if isinstance(storage, SQLiteStorage):
            storage.getloop = getloop
            storage.threadpool = threadpool_executor

        if serializer is None:
            serializer = (
                ExtendedJSONSerializer({"Message": Message, "Cron": Cron})
                if dumper is None and loader is None
                else JSONSerializer()
            )

        if dumper is None:
            dumper = DummyDumper()
        if loader is None:
            loader = DummyLoader()

        self.configs: JobifyConfiguration = JobifyConfiguration(
            tz=tz or ZoneInfo("UTC"),
            dumper=dumper,
            loader=loader,
            storage=storage,
            getloop=getloop,
            serializer=serializer,
            worker_pools=WorkerPools(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            cron_factory=cron_factory or create_crontab,
        )
        super().__init__(
            lifespan=lifespan,
            middleware=middleware,
            shared_state=SharedState(),
            jobify_config=self.configs,
            exception_handlers=exception_handlers,
        )

    def find_job(self, id_: str, /) -> Job[ReturnT] | None:
        """Find an active job by its ID.

        Args:
            id_: Unique identifier of the job.

        Returns:
            The `Job` instance if it's currently pending or running,
            otherwise `None`.

        """
        return self.task._shared_state.pending_jobs.get(id_)

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
            await jobify.wait_all()
            print("All jobs completed!")

            # Or with a timeout (raises asyncio.TimeoutError on timeout)
            try:
                await jobify.wait_all(timeout=30.0)
            except asyncio.TimeoutError:
                print("Timeout reached while waiting for jobs")
            ```

        """

        async def target() -> None:
            while jobs := self.task._shared_state.pending_jobs.values():
                coros = (job.wait() for job in jobs)
                _ = await asyncio.gather(*coros, return_exceptions=True)

        await asyncio.wait_for(target(), timeout=timeout)

    async def _restore_schedules(self) -> None:
        schedules = await self.configs.storage.get_schedules()
        for sch in schedules:
            if self.find_job(sch.job_id):
                msg = (
                    f"Job {sch.job_id} is already active (code defined)."
                    "Skipping DB restore."
                )
                logger.debug(msg)
                continue
            try:
                await self._feed_message(sch.message)
            except (KeyError, TypeError, ValueError) as exc:
                # KeyError: The function has been removed from the router
                #   (the code has changed).
                # TypeError: The arguments in the database do not match the new
                #   function signature.
                # ValueError: Serializer error.
                msg = (
                    f"Cannot restore job {sch.job_id} ({sch.func_name}). "
                    f"Exception Type: {type(exc)}. "
                    f"Reason: {exc}. Removing from storage."
                )
                logger.warning(msg)
                await self.configs.storage.delete_schedule(sch.job_id)
            except Exception:  # pragma: no cover
                msg = f"Unexpected error restoring job {sch.job_id}"
                logger.exception(msg)

    async def _feed_message(self, raw_msg: bytes) -> None:
        de_message = self.configs.serializer.loadb(raw_msg)
        msg = self.configs.loader.load(de_message, Message)
        route = self.task._routes[msg.func_name]
        for name, arg in msg.arguments.items():
            msg.arguments[name] = self.configs.loader.load(
                arg,
                route.func_spec.params_type[name],
            )
        bound = route.func_spec.signature.bind(**msg.arguments)
        builder = route.create_builder(bound)
        if "cron" in msg.trigger:
            _ = builder._cron(**msg.trigger)
        else:
            _ = builder._at(**msg.trigger)

    async def startup(self) -> None:
        """Initialize the Jobify application.

        This method:
        1. Marks the application as started
        2. Propagates startup events to all routers and their registrators
        3. Schedules any pending cron jobs

        Raises:
            RuntimeError: If application startup fails due to configuration
            issues or router initialization errors.

        """
        self.configs.app_started = True
        await self.configs.storage.startup()
        await self._propagate_startup(self)
        await self._restore_schedules()
        await self.task.start_pending_crons()

    async def shutdown(self) -> None:
        """Gracefully shut down the Jobify application.

        This method performs a structured shutdown:
        1. Marks the application as stopped (`app_started = False`).
        2. Propagates shutdown events to all routers/components.
        3. Cancels all scheduled future jobs in the registry
           (`_jobs_registry`).
        4. Closes the jobify configuration (e.g., stopping the internal
           scheduler).
        5. Cancels all currently running tasks (in `_tasks_registry`), waits
           for their completion, and explicitly clears the task registry.

        Note:
            The method uses `return_exceptions=True` when gathering cancelled
            tasks to prevent shutdown from being interrupted by task exception.

        """
        self.configs.app_started = False

        if tasks := self.task._shared_state.pending_tasks:  # pragma: no cover
            for task in tuple(tasks):
                _ = task.cancel()
            _ = await asyncio.gather(*tasks, return_exceptions=True)
            tasks.clear()

        if jobs := tuple(self.task._shared_state.pending_jobs.values()):
            for job in jobs:
                job._cancel()

        self.configs.worker_pools.close()
        await self._propagate_shutdown()
        await self.configs.storage.shutdown()

    async def __aenter__(self) -> Self:
        """Enter the Jobify context manager.

        Returns:
            The initialized Jobify instance ready for use.

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
        """Exit the Jobify context manager.

        Note:
            This method ensures proper shutdown regardless of whether an
            exception occurred in the managed context. The exception parameters
            are ignored as shutdown should proceed even if the context failed.

        """
        await self.shutdown()
