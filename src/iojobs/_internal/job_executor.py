from __future__ import annotations

import asyncio
import heapq
import textwrap
import traceback
import warnings
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Final, Generic, TypeVar, cast
from uuid import uuid4

from iojobs._internal._types import EMPTY, FuncID
from iojobs._internal.cron_parser import CronParser
from iojobs._internal.exceptions import (
    ConcurrentExecutionError,
    JobNotCompletedError,
    JobNotInitializedError,
    NegativeDelayError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from zoneinfo import ZoneInfo

    from iojobs._internal.executors import ExecutorPool

_R = TypeVar("_R")


class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    SUCCESS = "success"
    CANCELED = "canceled"
    ERROR = "error"


class JobInfo(Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_job_registered",
        "_result",
        "_timer_handler",
        "exec_at_timestamp",
        "func_id",
        "job_id",
        "status",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        job_id: str,
        exec_at_timestamp: float,
        func_id: str,
        timer_handler: asyncio.TimerHandle,
        job_registered: list[JobInfo[_R]],
        job_status: JobStatus,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._job_registered: list[JobInfo[_R]] = job_registered
        self._result: _R = EMPTY
        self._timer_handler: asyncio.TimerHandle = timer_handler
        self.exec_at_timestamp: float = exec_at_timestamp
        self.func_id: str = func_id
        self.job_id: str = job_id
        self.status: JobStatus = job_status

    def _update(
        self,
        *,
        job_id: str,
        exec_at_timestamp: float,
        timer_handler: asyncio.TimerHandle,
        job_status: JobStatus,
    ) -> None:
        self._event = asyncio.Event()
        self._timer_handler = timer_handler
        self.exec_at_timestamp = exec_at_timestamp
        self.job_id = job_id
        self.status = job_status

    def __repr__(self) -> str:
        return textwrap.dedent(f"""\
            {self.__class__.__name__}_\
            (instance_id={id(self)}, \
            exec_at_timestamp={self.exec_at_timestamp}, \
            func_id={self.func_id}, job_id={self.job_id})
        """)

    def __lt__(self, other: JobInfo[_R]) -> bool:
        return self.exec_at_timestamp < other.exec_at_timestamp

    def __gt__(self, other: JobInfo[_R]) -> bool:
        return self.exec_at_timestamp > other.exec_at_timestamp

    @property
    def result(self) -> _R:
        if self._result is EMPTY:
            raise JobNotCompletedError
        return self._result

    @result.setter
    def result(self, val: _R) -> None:
        self._result = val

    def is_done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        if self.is_done():
            warnings.warn(
                "Job is already done - waiting for completion is unnecessary",
                category=RuntimeWarning,
                stacklevel=2,
            )
            return
        _ = await self._event.wait()

    def cancel(self) -> None:
        self.status = JobStatus.CANCELED
        self._timer_handler.cancel()
        self._job_registered.remove(self)
        self._event.set()


class JobExecutor(ABC, Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_cron_parser",
        "_func_id",
        "_func_injected",
        "_is_cron",
        "_job_info",
        "_jobs_registered",
        "_loop",
        "_on_error_callback",
        "_on_success_callback",
        "_tz",
    )

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        func_injected: Callable[..., Coroutine[None, None, _R] | _R],
        jobs_registered: list[JobInfo[_R]],
        tz: ZoneInfo,
    ) -> None:
        self._func_id: FuncID = func_id
        self._func_injected: Callable[..., Coroutine[None, None, _R] | _R] = (
            func_injected
        )
        self._loop: asyncio.AbstractEventLoop = loop
        self._on_success_callback: list[Callable[[_R], None]] = []
        self._on_error_callback: list[Callable[[Exception], None]] = []
        self._job_info: JobInfo[_R] | None = None
        self._jobs_registered: Final = jobs_registered
        self._tz: Final = tz
        self._cron_parser: CronParser = EMPTY
        self._is_cron: bool = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is EMPTY:
            self._loop = asyncio.get_running_loop()
        return self._loop

    @property
    def job_info(self) -> JobInfo[_R]:
        if self._job_info is None:
            raise JobNotInitializedError
        return self._job_info

    @abstractmethod
    def _execute(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def to_thread(self) -> JobExecutor[_R]:
        raise NotImplementedError

    @abstractmethod
    def to_process(self) -> JobExecutor[_R]:
        raise NotImplementedError

    def on_success(self, *callbacks: Callable[[_R], None]) -> JobExecutor[_R]:
        self._on_success_callback.extend(callbacks)
        return self

    def on_error(
        self,
        *callbacks: Callable[[Exception], None],
    ) -> JobExecutor[_R]:
        self._on_error_callback.extend(callbacks)
        return self

    def call(self) -> _R:
        return cast("_R", self._func_injected())

    def cron(
        self,
        expression: str,
        /,
        *,
        to_thread: bool = EMPTY,
        to_process: bool = EMPTY,
    ) -> JobInfo[_R]:
        if self._cron_parser is EMPTY:
            self._cron_parser = CronParser(expression=expression)
            self._is_cron = True
        return self._schedule_cron(to_thread=to_thread, to_process=to_process)

    def _schedule_cron(
        self,
        *,
        to_thread: bool = EMPTY,
        to_process: bool = EMPTY,
    ) -> JobInfo[_R]:
        now = datetime.now(tz=self._tz)
        next_run = self._cron_parser.next_run(now=now)
        return self._at_execute(
            now=now,
            at=next_run,
            job_id=EMPTY,
            to_thread=to_thread,
            to_process=to_process,
        )

    def delay(
        self,
        delay_seconds: float,
        /,
        *,
        job_id: str = EMPTY,
        to_thread: bool = EMPTY,
        to_process: bool = EMPTY,
    ) -> JobInfo[_R]:
        now = datetime.now(tz=self._tz)
        at = now + timedelta(seconds=delay_seconds)
        return self._at_execute(
            now=now,
            at=at,
            job_id=job_id,
            to_thread=to_thread,
            to_process=to_process,
        )

    def at(
        self,
        at: datetime,
        /,
        *,
        job_id: str = EMPTY,
        to_thread: bool = EMPTY,
        to_process: bool = EMPTY,
    ) -> JobInfo[_R]:
        now = datetime.now(tz=at.tzinfo)
        return self._at_execute(
            now=now,
            at=at,
            job_id=job_id,
            to_thread=to_thread,
            to_process=to_process,
        )

    def _at_execute(
        self,
        *,
        now: datetime,
        at: datetime,
        job_id: str,
        to_thread: bool,
        to_process: bool,
    ) -> JobInfo[_R]:
        if to_thread and to_process:
            raise ConcurrentExecutionError
        if to_process is not EMPTY:
            _ = self.to_process()
        elif to_thread is not EMPTY:
            _ = self.to_thread()

        now_timestamp = now.timestamp()
        at_timestamp = at.timestamp()
        delay_seconds = at_timestamp - now_timestamp
        if delay_seconds < 0:
            raise NegativeDelayError(delay_seconds)

        loop = self.loop
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._execute)
        if self._job_info and self._is_cron:
            job_info = self._job_info
            job_info._update(  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
                job_id=uuid4().hex,
                exec_at_timestamp=at_timestamp,
                timer_handler=time_handler,
                job_status=JobStatus.SCHEDULED,
            )
        else:
            job_info = JobInfo[_R](
                exec_at_timestamp=at_timestamp,
                func_id=self._func_id,
                job_id=job_id or uuid4().hex,
                timer_handler=time_handler,
                job_registered=self._jobs_registered,
                job_status=JobStatus.SCHEDULED,
            )
            self._job_info = job_info
        heapq.heappush(self._jobs_registered, job_info)
        return job_info

    def _set_result(
        self,
        future_or_func: asyncio.Future[_R] | Callable[..., _R],
        /,
    ) -> None:
        try:
            if isinstance(future_or_func, asyncio.Future):
                future = future_or_func
                result = future.result()
            else:
                func = future_or_func
                result = func()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.job_info.status = JobStatus.ERROR
            self._run_hooks_error(exc)
        else:
            self.job_info.result = result
            self.job_info.status = JobStatus.SUCCESS
            self._run_hooks_success(result)
        finally:
            _ = heapq.heappop(self._jobs_registered)
            self.job_info._event.set()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
            if self._is_cron:
                _ = self._schedule_cron()

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


class JobExecutorSync(JobExecutor[_R]):
    __slots__: tuple[str, ...] = (
        "_executors",
        "_run_to_process",
        "_run_to_thread",
    )
    _func_injected: Callable[..., _R]

    def __init__(  # noqa: PLR0913
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        func_injected: Callable[..., _R],
        jobs_registered: list[JobInfo[_R]],
        executors: ExecutorPool,
        tz: ZoneInfo,
    ) -> None:
        self._executors: Final = executors
        self._run_to_process: bool = False
        self._run_to_thread: bool = False
        super().__init__(
            loop=loop,
            func_id=func_id,
            jobs_registered=jobs_registered,
            func_injected=func_injected,
            tz=tz,
        )

    def _execute(self) -> None:
        executor = EMPTY
        if self._run_to_process:
            executor = self._executors.processpool_executor
        elif self._run_to_thread:
            executor = self._executors.threadpool_executor

        if executor is not EMPTY:
            future = self.loop.run_in_executor(executor, self._func_injected)
            future.add_done_callback(self._set_result)
        else:
            self._set_result(self._func_injected)

    def to_thread(self) -> JobExecutor[_R]:
        self._run_to_thread = True
        return self

    def to_process(self) -> JobExecutor[_R]:
        self._run_to_process = True
        return self


class JobExecutorAsync(JobExecutor[_R]):
    _func_injected: Callable[..., Coroutine[None, None, _R]]

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        func_injected: Callable[..., Coroutine[None, None, _R]],
        jobs_registered: list[JobInfo[_R]],
        tz: ZoneInfo,
    ) -> None:
        super().__init__(
            loop=loop,
            func_id=func_id,
            jobs_registered=jobs_registered,
            func_injected=func_injected,
            tz=tz,
        )

    def _execute(self) -> None:
        coro_task = asyncio.create_task(self._func_injected())
        coro_task.add_done_callback(self._set_result)

    def to_thread(self) -> JobExecutorAsync[_R]:
        warnings.warn(
            ASYNC_FUNC_IGNORED_WARNING.format(fname="to_thread"),
            category=RuntimeWarning,
            stacklevel=2,
        )
        return self

    def to_process(self) -> JobExecutor[_R]:
        warnings.warn(
            ASYNC_FUNC_IGNORED_WARNING.format(fname="to_process"),
            category=RuntimeWarning,
            stacklevel=2,
        )
        return self


ASYNC_FUNC_IGNORED_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""
