# pyright: reportPrivateUsage=false
# ruff: noqa: SLF001
from __future__ import annotations

import asyncio
import contextlib
import heapq
import traceback
import warnings
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Generic, TypeVar, cast
from uuid import uuid4

from iojobs._internal._types import EMPTY, FAILED, JobExtras
from iojobs._internal.command_runner import (
    AsyncRunner,
    ExecutorPoolRunner,
    SyncRunner,
)
from iojobs._internal.cron_parser import CronParser
from iojobs._internal.enums import ExecutionMode, JobStatus
from iojobs._internal.exceptions import (
    JobFailedError,
    JobNotCompletedError,
    JobNotInitializedError,
    NegativeDelayError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from zoneinfo import ZoneInfo

    from iojobs._internal.command_runner import CommandRunner
    from iojobs._internal.executors_pool import ExecutorPool

_R = TypeVar("_R")


class Job(Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_exception",
        "_is_was_waiting",
        "_job_registered",
        "_result",
        "_timer_handler",
        "exec_at_timestamp",
        "func_name",
        "job_id",
        "status",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        job_id: str,
        exec_at_timestamp: float,
        func_name: str,
        timer_handler: asyncio.TimerHandle,
        job_registered: list[Job[_R]],
        job_status: JobStatus,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._job_registered: list[Job[_R]] = job_registered
        self._result: _R = EMPTY
        self._exception: Exception = EMPTY
        self._is_was_waiting: bool = False
        self._timer_handler: asyncio.TimerHandle = timer_handler
        self.exec_at_timestamp: float = exec_at_timestamp
        self.func_name: str = func_name
        self.job_id: str = job_id
        self.status: JobStatus = job_status

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}("
            f"instance_id={id(self)}, "
            f"exec_at_timestamp={self.exec_at_timestamp}, "
            f"func_name={self.func_name}, job_id={self.job_id})"
        )

    def __lt__(self, other: Job[_R]) -> bool:
        return self.exec_at_timestamp < other.exec_at_timestamp

    def __gt__(self, other: Job[_R]) -> bool:
        return self.exec_at_timestamp > other.exec_at_timestamp

    def result(self) -> _R:
        if self._result is FAILED:
            raise JobFailedError(self.job_id, reason=str(self._exception))
        if self._result is EMPTY:
            raise JobNotCompletedError
        return self._result

    def set_result(self, val: _R) -> None:
        self._result = val

    def set_exception(self, exc: Exception) -> None:
        self._exception = exc

    def _update(
        self,
        *,
        job_id: str,
        exec_at_timestamp: float,
        timer_handler: asyncio.TimerHandle,
        job_status: JobStatus,
    ) -> None:
        self._event = asyncio.Event()
        self._is_was_waiting = False
        self._timer_handler = timer_handler
        self.exec_at_timestamp = exec_at_timestamp
        self.job_id = job_id
        self.status = job_status

    def is_done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        if self._is_was_waiting:
            warnings.warn(
                "Job is already done - waiting for completion is unnecessary",
                category=RuntimeWarning,
                stacklevel=2,
            )
            return

        _ = await self._event.wait()
        self._is_was_waiting = True

    def cancel(self) -> None:
        self.status = JobStatus.CANCELED
        self._timer_handler.cancel()
        with contextlib.suppress(ValueError):
            self._job_registered.remove(self)
        self._event.set()


class JobRunner(ABC, Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_asyncio_tasks",
        "_cron_parser",
        "_extras",
        "_func_injected",
        "_func_name",
        "_is_cron",
        "_job",
        "_jobs_registered",
        "_loop",
        "_on_error_callback",
        "_on_success_callback",
        "_tz",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo,
        loop: asyncio.AbstractEventLoop,
        func_name: str,
        func_injected: Callable[..., Coroutine[object, object, _R] | _R],
        jobs_registered: list[Job[_R]],
        asyncio_tasks: list[asyncio.Task[_R]],
        extras: JobExtras,
    ) -> None:
        self._func_name: str = func_name
        self._func_injected: Callable[
            ...,
            Coroutine[object, object, _R] | _R,
        ] = func_injected
        self._tz: Final = tz
        self._loop: asyncio.AbstractEventLoop = loop
        self._on_success_callback: list[Callable[[_R], None]] = []
        self._on_error_callback: list[Callable[[Exception], None]] = []
        self._job: Job[_R] | None = None
        self._jobs_registered: Final = jobs_registered
        self._cron_parser: CronParser = EMPTY
        self._is_cron: bool = False
        self._asyncio_tasks: list[asyncio.Task[_R]] = asyncio_tasks
        self._extras: JobExtras = extras

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is EMPTY:
            self._loop = asyncio.get_running_loop()
        return self._loop

    @property
    def job(self) -> Job[_R]:
        if self._job is None:
            raise JobNotInitializedError
        return self._job

    @abstractmethod
    def _execute(self, execution_mode: ExecutionMode) -> None:
        raise NotImplementedError

    @abstractmethod
    def _to_thread_validate(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _to_process_validate(self) -> None:
        raise NotImplementedError

    async def cron(
        self,
        expression: str,
        /,
        *,
        now: datetime = EMPTY,
        execution_mode: ExecutionMode = ExecutionMode.MAIN,
    ) -> Job[_R]:
        self._is_cron = True
        if self._cron_parser is EMPTY:
            self._cron_parser = CronParser(expression=expression)
        return await self._schedule_cron(
            now=now or datetime.now(tz=self._tz),
            execution_mode=execution_mode,
        )

    async def _schedule_cron(
        self,
        *,
        now: datetime,
        execution_mode: ExecutionMode,
    ) -> Job[_R]:
        next_run = self._cron_parser.next_run(now=now)
        return await self._at_execute(
            at=next_run,
            now=now,
            job_id=EMPTY,
            execution_mode=execution_mode,
        )

    async def delay(
        self,
        delay_seconds: float,
        /,
        *,
        now: datetime = EMPTY,
        job_id: str = EMPTY,
        execution_mode: ExecutionMode = ExecutionMode.MAIN,
    ) -> Job[_R]:
        now = now or datetime.now(tz=self._tz)
        at = now + timedelta(seconds=delay_seconds)
        return await self._at_execute(
            now=now,
            at=at,
            job_id=job_id,
            execution_mode=execution_mode,
        )

    async def at(
        self,
        at: datetime,
        /,
        *,
        now: datetime = EMPTY,
        job_id: str = EMPTY,
        execution_mode: ExecutionMode = ExecutionMode.MAIN,
    ) -> Job[_R]:
        now = now or datetime.now(tz=at.tzinfo)
        return await self._at_execute(
            now=now,
            at=at,
            job_id=job_id,
            execution_mode=execution_mode,
        )

    async def _at_execute(
        self,
        *,
        now: datetime,
        at: datetime,
        job_id: str,
        execution_mode: ExecutionMode,
    ) -> Job[_R]:
        if execution_mode is ExecutionMode.PROCESS:
            _ = self._to_process_validate()
        elif execution_mode is ExecutionMode.THREAD:
            _ = self._to_thread_validate()

        now_timestamp = now.timestamp()
        at_timestamp = at.timestamp()
        delay_seconds = at_timestamp - now_timestamp
        if delay_seconds < 0:
            raise NegativeDelayError(delay_seconds)

        loop = self.loop
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._execute, execution_mode)
        if self._job and self._is_cron:
            job = self._job
            job._update(
                job_id=uuid4().hex,
                exec_at_timestamp=at_timestamp,
                timer_handler=time_handler,
                job_status=JobStatus.SCHEDULED,
            )
        else:
            job = Job[_R](
                exec_at_timestamp=at_timestamp,
                func_name=self._func_name,
                job_id=job_id or uuid4().hex,
                timer_handler=time_handler,
                job_registered=self._jobs_registered,
                job_status=JobStatus.SCHEDULED,
            )
            self._job = job
        heapq.heappush(self._jobs_registered, job)
        return job

    async def _runner(
        self,
        *,
        cmd: CommandRunner[_R],
        execution_mode: ExecutionMode,
    ) -> _R:
        job = self.job
        try:
            result = await cmd.run()
        except Exception as exc:
            traceback.print_exc()
            job.status = JobStatus.FAILED
            job.set_result(FAILED)
            job.set_exception(exc)
            self._run_hooks_error(exc)
            raise
        else:
            job.set_result(result)
            job.status = JobStatus.SUCCESS
            self._run_hooks_success(result)
            return result
        finally:
            _ = heapq.heappop(self._jobs_registered)
            task = cast("asyncio.Task[_R]", asyncio.current_task())
            self._asyncio_tasks.remove(task)
            self.job._event.set()
            if self._is_cron:
                _ = await self._schedule_cron(
                    now=datetime.now(tz=self._tz),
                    execution_mode=execution_mode,
                )

    def on_success(self, *callbacks: Callable[[_R], None]) -> JobRunner[_R]:
        self._on_success_callback.extend(callbacks)
        return self

    def on_error(
        self,
        *callbacks: Callable[[Exception], None],
    ) -> JobRunner[_R]:
        self._on_error_callback.extend(callbacks)
        return self

    def _run_hooks_success(self, result: _R) -> None:
        for call_success in self._on_success_callback:
            try:
                call_success(result)
            except Exception:  # noqa: BLE001, PERF203
                traceback.print_exc()

    def _run_hooks_error(self, exc: Exception) -> None:
        for call_error in self._on_error_callback:
            try:
                call_error(exc)
            except Exception:  # noqa: BLE001, PERF203
                traceback.print_exc()


class JobRunnerSync(JobRunner[_R]):
    __slots__: tuple[str, ...] = ("_executors",)
    _func_injected: Callable[..., _R]

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo,
        loop: asyncio.AbstractEventLoop,
        func_name: str,
        func_injected: Callable[..., _R],
        jobs_registered: list[Job[_R]],
        executors: ExecutorPool,
        asyncio_tasks: list[asyncio.Task[_R]],
        extras: JobExtras,
    ) -> None:
        self._executors: Final = executors
        super().__init__(
            tz=tz,
            loop=loop,
            func_name=func_name,
            jobs_registered=jobs_registered,
            func_injected=func_injected,
            asyncio_tasks=asyncio_tasks,
            extras=extras,
        )

    def _execute(self, execution_mode: ExecutionMode) -> None:
        executor = EMPTY
        match execution_mode:
            case ExecutionMode.PROCESS:
                executor = self._executors.processpool_executor
            case ExecutionMode.THREAD:
                executor = self._executors.threadpool_executor
            case _:
                pass

        cmd: SyncRunner[_R] | ExecutorPoolRunner[_R]
        if executor is EMPTY:
            cmd = SyncRunner(self._func_injected)
        else:
            cmd = ExecutorPoolRunner(self._func_injected, executor, self.loop)

        task = asyncio.create_task(
            self._runner(cmd=cmd, execution_mode=execution_mode),
        )
        self._asyncio_tasks.append(task)

    def _to_thread_validate(self) -> None:
        pass

    def _to_process_validate(self) -> None:
        pass


class JobRunnerAsync(JobRunner[_R]):
    _func_injected: Callable[..., Coroutine[object, object, _R]]

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo,
        loop: asyncio.AbstractEventLoop,
        func_name: str,
        func_injected: Callable[..., Coroutine[object, object, _R]],
        jobs_registered: list[Job[_R]],
        asyncio_tasks: list[asyncio.Task[_R]],
        extras: JobExtras,
    ) -> None:
        super().__init__(
            tz=tz,
            loop=loop,
            func_name=func_name,
            jobs_registered=jobs_registered,
            func_injected=func_injected,
            asyncio_tasks=asyncio_tasks,
            extras=extras,
        )

    def _execute(self, execution_mode: ExecutionMode) -> None:
        if execution_mode is not ExecutionMode.MAIN:
            pass  # In async functions, runs only in the ExecutionMode.MAIN

        cmd = AsyncRunner(self._func_injected)
        task = asyncio.create_task(
            self._runner(
                cmd=cmd,
                execution_mode=execution_mode,
            ),
        )
        self._asyncio_tasks.append(task)

    def _to_thread_validate(self) -> None:
        warnings.warn(
            ASYNC_FUNC_IGNORED_WARNING.format(fname="to_thread"),
            category=RuntimeWarning,
            stacklevel=2,
        )

    def _to_process_validate(self) -> None:
        warnings.warn(
            ASYNC_FUNC_IGNORED_WARNING.format(fname="to_process"),
            category=RuntimeWarning,
            stacklevel=2,
        )


ASYNC_FUNC_IGNORED_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""
