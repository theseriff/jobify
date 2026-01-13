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
from jobify._internal.message import AtArguments, CronArguments, Message
from jobify._internal.router.root import (
    PENDING_CRON_JOBS,
    PendingCronJobs,
    RootRouter,
)
from jobify._internal.scheduler.misfire_policy import (
    GracePolicy,
    MisfirePolicy,
)
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
    from jobify._internal.storage.abc import ScheduledJob, Storage
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
        cron_factory: CronFactory = create_crontab,
        loop_factory: LoopFactory = asyncio.get_running_loop,
        exception_handlers: MappingExceptionHandlers | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
    ) -> None:
        """Initialize a `Jobify` instance."""
        getloop = cache_result(loop_factory)
        tz = tz or ZoneInfo("UTC")

        if storage is False:
            storage = DummyStorage()
        elif storage is None:
            storage = SQLiteStorage()

        if isinstance(storage, SQLiteStorage):
            storage.getloop = getloop
            storage.threadpool = threadpool_executor
            storage.tz = tz

        if serializer is None:
            system_types = (
                Message,
                Cron,
                CronArguments,
                AtArguments,
                MisfirePolicy,
                GracePolicy,
            )
            serializer = (
                ExtendedJSONSerializer(system_types)
                if dumper is None and loader is None
                else JSONSerializer()
            )

        if dumper is None:
            dumper = DummyDumper()
        if loader is None:
            loader = DummyLoader()

        self.configs: JobifyConfiguration = JobifyConfiguration(
            tz=tz,
            dumper=dumper,
            loader=loader,
            storage=storage,
            getloop=getloop,
            serializer=serializer,
            worker_pools=WorkerPools(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            cron_factory=cron_factory,
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

    async def _start_pending_crons(
        self,
        db_map: dict[str, ScheduledJob],
    ) -> None:
        pending_crons: PendingCronJobs = self.state.pop(PENDING_CRON_JOBS, {})
        scheduled_to_update: list[ScheduledJob] = []

        for job_id, (route, cron) in pending_crons.items():
            builder = route.schedule()
            real_now = builder.now()
            cron_parser = self.configs.cron_factory(cron.expression)
            next_run_at = cron_parser.next_run(now=real_now)

            if not builder._is_persist():
                _ = builder._cron(
                    cron=cron,
                    job_id=job_id,
                    next_run_at=next_run_at,
                    real_now=real_now,
                    cron_parser=cron_parser,
                )
                continue

            if scheduled := db_map.get(job_id):
                try:
                    deserializer = self.configs.serializer.loadb
                    loader = self.configs.loader.load
                    msg = loader(deserializer(scheduled.message), Message)
                    if isinstance(msg.trigger, CronArguments):
                        next_run_at = cron_parser.next_run(
                            now=msg.trigger.offset,
                        )
                except (ValueError, TypeError) as exc:
                    warn = (
                        "Failed to parse existing scheduled cron job. "
                        f"Exception: {exc}"
                    )
                    logger.warning(warn)

            new_trigger = CronArguments(cron, job_id, real_now)
            scheduled = builder._create_scheduled(
                trigger=new_trigger,
                job_id=job_id,
                next_run_at=next_run_at,
            )
            scheduled_to_update.append(scheduled)
            db_map[job_id] = scheduled

        await self.configs.storage.add_schedule(*scheduled_to_update)

    async def _restore_schedules(self) -> None:
        db_map = {
            sch.job_id: sch
            for sch in await self.configs.storage.get_schedules()
        }
        await self._start_pending_crons(db_map)

        scheduled_to_delete: list[str] = []
        for sch in db_map.values():
            route = self.task._routes.get(sch.func_name, ...)
            if route is ... or route.options.get("durable") is False:
                scheduled_to_delete.append(sch.job_id)
                continue
            try:
                self._feed_message(sch)
            except (KeyError, TypeError, ValueError) as exc:
                # KeyError: The function has been removed from the router
                #   (the code has changed).
                # TypeError: The arguments in the database do not match the new
                #   function signature.
                # ValueError: Serializer error.
                msg = (
                    f"Cannot restore <job_id {sch.job_id!r}>"
                    f"<func_name {sch.func_name!r}>.\n"
                    f"Exception Type: {type(exc)}. "
                    f"Reason: {exc}. Removing from storage."
                )
                logger.warning(msg)
                scheduled_to_delete.append(sch.job_id)
            except Exception:  # pragma: no cover
                msg = f"Unexpected error restoring job {sch.job_id}"
                logger.exception(msg)
                scheduled_to_delete.append(sch.job_id)

        await self.configs.storage.delete_schedule_many(scheduled_to_delete)

    def _feed_message(self, sch: ScheduledJob) -> None:
        deserializer = self.configs.serializer.loadb
        loader = self.configs.loader.load

        msg = loader(deserializer(sch.message), Message)
        route = self.task._routes[msg.func_name]
        for name, raw_arg in msg.arguments.items():
            param_type = route.func_spec.params_type[name]
            msg.arguments[name] = loader(raw_arg, param_type)

        bound = route.func_spec.signature.bind(**msg.arguments)
        builder = route.create_builder(bound)
        real_now = builder.now()

        match msg.trigger:
            case CronArguments(cron, job_id):
                cron_parser = self.configs.cron_factory(cron.expression)
                _ = builder._cron(
                    cron=cron,
                    job_id=job_id,
                    next_run_at=sch.next_run_at,
                    real_now=real_now,
                    cron_parser=cron_parser,
                )
            case AtArguments(at, job_id):
                _ = builder._at(at=at, job_id=job_id, real_now=real_now)

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
