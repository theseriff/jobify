"""Jobify entrypoint."""

from __future__ import annotations

import asyncio
import functools
import logging
import signal
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, ParamSpec, TypeVar
from zoneinfo import ZoneInfo

from typing_extensions import Self

from jobify._internal.common.constants import EMPTY, PATCH_CRON_DEF_ID
from jobify._internal.configuration import (
    Cron,
    JobifyConfiguration,
    WorkerPools,
)
from jobify._internal.message import AtArguments, CronArguments, Message
from jobify._internal.router.root import (
    CRONS_DEF_KEY,
    CronsDefinition,
    RootRoute,
    RootRouter,
)
from jobify._internal.scheduler.misfire_policy import (
    GracePolicy,
    MisfirePolicy,
    handle_misfire_policy,
)
from jobify._internal.serializers.json import JSONSerializer
from jobify._internal.serializers.json_extended import ExtendedJSONSerializer
from jobify._internal.shared_state import SharedState
from jobify._internal.storage.abc import ScheduledJob
from jobify._internal.storage.dummy import DummyStorage
from jobify._internal.storage.sqlite import SQLiteStorage
from jobify._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobify.crontab import create_crontab

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from datetime import datetime
    from types import FrameType, TracebackType

    from jobify._internal.common.types import Lifespan, LoopFactory
    from jobify._internal.cron_parser import CronFactory, CronParser
    from jobify._internal.middleware.base import BaseMiddleware
    from jobify._internal.middleware.exceptions import MappingExceptionHandlers
    from jobify._internal.scheduler.job import Job
    from jobify._internal.scheduler.scheduler import ScheduleBuilder
    from jobify._internal.serializers.base import Serializer
    from jobify._internal.storage.abc import Storage
    from jobify._internal.typeadapter.base import Dumper, Loader

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)
if sys.platform == "win32":  # pragma: no cover
    # Windows signal 21. Sent by Ctrl+Break.
    HANDLED_SIGNALS += (signal.SIGBREAK,)  # pyright: ignore[reportConstantRedefinition]

logger = logging.getLogger("Jobify")

AppT = TypeVar("AppT", bound="Jobify")
ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")


@dataclass(slots=True)
class _CronSchedule:
    arg: CronArguments
    builder: ScheduleBuilder[Any]
    next_run_at: datetime
    cron_parser: CronParser


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
        storage: Storage | Literal[False] = EMPTY,
        lifespan: Lifespan[AppT] | None = None,
        serializer: Serializer | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
        cron_factory: CronFactory = create_crontab,
        loop_factory: LoopFactory = asyncio.get_running_loop,
        exception_handlers: MappingExceptionHandlers | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
        route_class: type[RootRoute[..., Any]] = RootRoute,
    ) -> None:
        """Initialize a `Jobify` instance."""
        getloop = cache_result(loop_factory)
        tz = tz or ZoneInfo("UTC")

        if storage is False:
            storage = DummyStorage()
        elif storage is EMPTY:
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
            route_class=route_class,
        )
        self._captured_signals: list[int] = []

    def find_job(self, id_: str, /) -> Job[ReturnT] | None:
        """Find an active job by its ID.

        Args:
            id_: Unique identifier of the job.

        Returns:
            The `Job` instance if it's currently pending or running,
            otherwise `None`.

        """
        return self.task._shared_state.pending_jobs.get(id_)

    def get_active_jobs(self) -> list[Job[Any]]:
        """Return a list of all currently active jobs."""
        return list(self.task._shared_state.pending_jobs.values())

    async def __aenter__(self) -> Self:
        """Enter the Jobify context manager.

        Returns:
            The initialized Jobify instance ready for use.

        Raises:
            Any exception raised by `startup()` method.

        """
        await self.startup()
        return self

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

    async def _restore_schedules(self) -> None:  # noqa: C901
        crons_def: CronsDefinition = self.state.pop(CRONS_DEF_KEY, {})
        schedules = await self.configs.storage.get_schedules()
        db_map = {sch.job_id: sch for sch in schedules}

        at_args: dict[str, tuple[ScheduleBuilder[Any], AtArguments]] = {}
        crons_args: dict[str, _CronSchedule] = {}
        crons_def_persist: set[str] = set()
        scheduled_to_update: list[ScheduledJob] = []
        scheduled_to_delete: list[str] = []

        for job_id, (rout, cron) in crons_def.items():
            builder = rout.schedule()
            offset = builder.now()

            cron_parser = self.configs.cron_factory(cron.expression)
            next_run_at = cron_parser.next_run(now=offset)
            trigger = CronArguments(cron, job_id, offset)
            crons_args[job_id] = _CronSchedule(
                trigger,
                builder,
                next_run_at,
                cron_parser,
            )
            if builder._is_persist():
                if job_id in db_map:
                    crons_def_persist.add(job_id)
                else:
                    scheduled_to_update.append(
                        ScheduledJob.create(
                            job_id,
                            builder.name,
                            builder._serialize_job_message(trigger),
                            next_run_at,
                        )
                    )

        loadb = self.configs.serializer.loadb
        type_adaptive = self.configs.loader.load

        for job_id, sch in db_map.items():
            route = self.task._routes.get(sch.name, ...)
            if (
                route is ...
                or route.options.get("durable") is False
                or (
                    job_id.endswith(PATCH_CRON_DEF_ID)
                    and job_id not in crons_def
                )
            ):
                scheduled_to_delete.append(job_id)
                continue
            try:
                msg = type_adaptive(loadb(sch.message), Message)
                for name, raw_arg in msg.arguments.items():
                    param_type = route.func_spec.params_type[name]
                    msg.arguments[name] = type_adaptive(raw_arg, param_type)
                bound = route.func_spec.signature.bind(**msg.arguments)
            except (KeyError, TypeError, ValueError) as exc:
                # KeyError: The function has been removed from the router
                #   (the code has changed).
                # TypeError: The arguments in the database do not match the new
                #   function signature.
                # ValueError: Serializer error.
                warn = (
                    f"Cannot restore <job_id {job_id!r}>"
                    f"<name {sch.name!r}>.\n"
                    f"Exception Type: {type(exc)}. "
                    f"Reason: {exc}. Removing from storage."
                )
                logger.warning(warn)
                scheduled_to_delete.append(job_id)
            except Exception:  # pragma: no cover
                err = f"Unexpected error restoring job {job_id}"
                logger.exception(err)
                scheduled_to_delete.append(job_id)
            else:
                builder = route.create_builder(bound)
                self._handle_trigger(
                    msg.trigger,
                    builder,
                    scheduled_to_update,
                    crons_def_persist,
                    crons_args,
                    at_args,
                )
        if scheduled_to_update:
            update_ids = [job.job_id for job in scheduled_to_update]
            logger.info(
                "Updating/Restoring %d schedules in storage: %s",
                len(update_ids),
                update_ids,
            )
        if scheduled_to_delete:
            logger.info(
                "Deleting %d obsolete schedules from storage: %s",
                len(scheduled_to_delete),
                scheduled_to_delete,
            )
        await self.configs.storage.add_schedule(*scheduled_to_update)
        await self.configs.storage.delete_schedule_many(scheduled_to_delete)
        self._start_pending_schedules(crons_args, at_args)

    def _handle_trigger(  # noqa: PLR0913
        self,
        trigger: CronArguments | AtArguments,
        builder: ScheduleBuilder[Any],
        scheduled_to_update: list[ScheduledJob],
        crons_declare_persist: set[str],
        crons_args: dict[str, _CronSchedule],
        at_args: dict[str, tuple[ScheduleBuilder[Any], AtArguments]],
    ) -> None:
        match trigger:
            case CronArguments(db_cron, job_id, db_offset) as trigger:
                if job_id in crons_declare_persist:
                    origin = crons_args[job_id]
                    new_cron = origin.arg.cron
                    new_builder = origin.builder

                    offset, next_run_at = new_builder._calculate_next_run_at(
                        old_cron=db_cron,
                        new_cron=new_cron,
                        real_now=new_builder.now(),
                        parser=origin.cron_parser,
                        offset=db_offset,
                    )
                    trigger.cron = new_cron
                    trigger.run_count = 0
                    trigger.offset = offset
                    origin.arg.run_count = 0
                    origin.arg.offset = offset
                    origin.next_run_at = next_run_at
                    scheduled_to_update.append(
                        ScheduledJob.create(
                            job_id,
                            builder.name,
                            builder._serialize_job_message(trigger),
                            next_run_at,
                        )
                    )
                else:
                    parser = self.configs.cron_factory(db_cron.expression)
                    next_run_at = handle_misfire_policy(
                        parser,
                        parser.next_run(now=db_offset),
                        builder.now(),
                        db_cron.misfire_policy,
                    )
                    crons_args[job_id] = _CronSchedule(
                        trigger,
                        builder,
                        next_run_at,
                        parser,
                    )
            case AtArguments(_, job_id) as trigger:
                at_args[job_id] = (builder, trigger)

    def _start_pending_schedules(
        self,
        crons_args: dict[str, _CronSchedule],
        at_args: dict[str, tuple[ScheduleBuilder[Any], AtArguments]],
    ) -> None:
        for cron in crons_args.values():
            _ = cron.builder._create_cron_job(
                cron=cron.arg.cron,
                job_id=cron.arg.job_id,
                next_run_at=cron.next_run_at,
                cron_parser=cron.cron_parser,
                offset=cron.arg.offset,
                run_count=cron.arg.run_count,
            )
        for builder, arg in at_args.values():
            _ = builder._at(arg.at, arg.job_id)

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

        if jobs := tuple(self.task._shared_state.pending_jobs.values()):
            for job in jobs:
                job._cancel()

        if tasks := self.task._shared_state.pending_tasks:  # pragma: no cover
            for task in tuple(tasks):
                _ = task.cancel()
            _ = await asyncio.gather(*tasks, return_exceptions=True)

        self.configs.worker_pools.close()
        await self._propagate_shutdown()
        await self.configs.storage.shutdown()

        # If we did gracefully shut down due to a signal, try to
        # trigger the expected behaviour now; multiple signals would be
        # done LIFO, see https://stackoverflow.com/questions/48434964
        for captured_signal in reversed(self._captured_signals):
            signal.raise_signal(captured_signal)

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

        """
        idle_event = self.task._shared_state.idle_event
        with self._capture_signals():
            _ = await asyncio.wait_for(idle_event.wait(), timeout=timeout)

    @contextmanager
    def _capture_signals(self) -> Iterator[None]:
        # Signals can only be listened to from the main thread.
        if threading.current_thread() is not threading.main_thread():
            yield
            return
        # always use signal.signal, even if loop.add_signal_handler is
        # available this allows to restore previous signal handlers later on
        original_handlers = {
            sig: signal.signal(sig, self._handle_exit)
            for sig in HANDLED_SIGNALS
        }
        try:
            yield
        finally:
            for sig, handler in original_handlers.items():
                _ = signal.signal(sig, handler)

    def _handle_exit(self, sig: int, _: FrameType | None) -> None:
        self._captured_signals.append(sig)
        loop = self.configs.getloop()
        idle_event = self.task._shared_state.idle_event
        _handle = loop.call_soon_threadsafe(idle_event.set)
