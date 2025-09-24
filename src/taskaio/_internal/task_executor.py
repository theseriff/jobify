from __future__ import annotations

import asyncio
import concurrent.futures
import heapq
import textwrap
import traceback
import warnings
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Generic, TypeVar, cast
from uuid import uuid4

from taskaio._internal._types import EMPTY, FuncID
from taskaio._internal.cron_parser import CronParser
from taskaio._internal.exceptions import (
    NegativeDelayError,
    TaskNotCompletedError,
    TaskNotInitializedError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from zoneinfo import ZoneInfo

_R = TypeVar("_R")


class TaskInfo(Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_result",
        "_task_registered",
        "_timer_handler",
        "exec_at_timestamp",
        "func_id",
        "task_id",
    )

    def __init__(
        self,
        *,
        task_id: str,
        exec_at_timestamp: float,
        func_id: str,
        timer_handler: asyncio.TimerHandle,
        task_registered: list[TaskInfo[_R]],
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._result: _R = EMPTY
        self._task_registered: list[TaskInfo[_R]] = task_registered
        self._timer_handler: asyncio.TimerHandle = timer_handler
        self.exec_at_timestamp: float = exec_at_timestamp
        self.func_id: str = func_id
        self.task_id: str = task_id

    def _update(
        self,
        *,
        task_id: str,
        exec_at_timestamp: float,
        timer_handler: asyncio.TimerHandle,
    ) -> None:
        self._event = asyncio.Event()
        self.exec_at_timestamp = exec_at_timestamp
        self.task_id = task_id
        self._timer_handler = timer_handler

    def __repr__(self) -> str:
        return textwrap.dedent(f"""\
            {self.__class__.__name__}_\
            (instance_id={id(self)}, \
            exec_at_timestamp={self.exec_at_timestamp}, \
            func_id={self.func_id}, task_id={self.task_id})
        """)

    def __lt__(self, other: TaskInfo[_R]) -> bool:
        return self.exec_at_timestamp < other.exec_at_timestamp

    def __gt__(self, other: TaskInfo[_R]) -> bool:
        return self.exec_at_timestamp > other.exec_at_timestamp

    @property
    def result(self) -> _R:
        if self._result is EMPTY:
            raise TaskNotCompletedError
        return self._result

    @result.setter
    def result(self, val: _R) -> None:
        self._result = val

    def is_done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        if self.is_done():
            warnings.warn(
                "Task is already done - waiting for completion is unnecessary",
                category=RuntimeWarning,
                stacklevel=2,
            )
            return
        _ = await self._event.wait()

    def cancel(self) -> None:
        self._timer_handler.cancel()
        self._task_registered.remove(self)
        self._event.set()


class TaskExecutor(ABC, Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_cron_parser",
        "_func_id",
        "_func_injected",
        "_is_cron",
        "_loop",
        "_on_error_callback",
        "_on_success_callback",
        "_run_to_thread",
        "_task_info",
        "_task_registered",
        "_tz",
    )

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        func_injected: Callable[..., Coroutine[None, None, _R] | _R],
        task_registered: list[TaskInfo[_R]],
        tz: ZoneInfo,
    ) -> None:
        self._func_id: FuncID = func_id
        self._func_injected: Callable[..., Coroutine[None, None, _R] | _R] = (
            func_injected
        )
        self._loop: asyncio.AbstractEventLoop = loop
        self._on_success_callback: list[Callable[[_R], None]] = []
        self._on_error_callback: list[Callable[[Exception], None]] = []
        self._run_to_thread: bool = False
        self._task_info: TaskInfo[_R] | None = None
        self._task_registered: Final = task_registered
        self._tz: Final = tz
        self._cron_parser: CronParser = EMPTY
        self._is_cron: bool = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is EMPTY:
            self._loop = asyncio.get_running_loop()
        return self._loop

    @property
    def task_info(self) -> TaskInfo[_R]:
        if self._task_info is None:
            raise TaskNotInitializedError
        return self._task_info

    @abstractmethod
    def _execute(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def to_thread(self) -> TaskExecutor[_R]:
        raise NotImplementedError

    def on_success(self, *callbacks: Callable[[_R], None]) -> TaskExecutor[_R]:
        self._on_success_callback.extend(callbacks)
        return self

    def on_error(
        self,
        *callbacks: Callable[[Exception], None],
    ) -> TaskExecutor[_R]:
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
    ) -> TaskInfo[_R]:
        self._is_cron = True
        if self._cron_parser is EMPTY:
            self._cron_parser = CronParser(expression=expression)
        return self._schedule_cron(to_thread=to_thread)

    def _schedule_cron(self, *, to_thread: bool = EMPTY) -> TaskInfo[_R]:
        now = datetime.now(tz=self._tz)
        next_run = self._cron_parser.next_run(now=now)
        return self._at_execute(
            now=now,
            at=next_run,
            task_id=EMPTY,
            to_thread=to_thread,
        )

    def delay(
        self,
        delay_seconds: float,
        /,
        *,
        task_id: str = EMPTY,
        to_thread: bool = EMPTY,
    ) -> TaskInfo[_R]:
        now = datetime.now(tz=self._tz)
        at = now + timedelta(seconds=delay_seconds)
        return self._at_execute(
            now=now,
            at=at,
            task_id=task_id,
            to_thread=to_thread,
        )

    def at(
        self,
        at: datetime,
        /,
        *,
        task_id: str = EMPTY,
        to_thread: bool = EMPTY,
    ) -> TaskInfo[_R]:
        now = datetime.now(tz=at.tzinfo)
        return self._at_execute(
            now=now,
            at=at,
            task_id=task_id,
            to_thread=to_thread,
        )

    def _at_execute(
        self,
        *,
        now: datetime,
        at: datetime,
        task_id: str,
        to_thread: bool,
    ) -> TaskInfo[_R]:
        if to_thread is not EMPTY:
            _ = self.to_thread()

        now_timestamp = now.timestamp()
        at_timestamp = at.timestamp()
        delay_seconds = at_timestamp - now_timestamp
        if delay_seconds < 0:
            raise NegativeDelayError(delay_seconds)

        loop = self.loop
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._execute)
        if self._task_info and self._is_cron:
            task_info = self._task_info
            task_info._update(  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
                task_id=uuid4().hex,
                exec_at_timestamp=at_timestamp,
                timer_handler=time_handler,
            )
        else:
            task_info = TaskInfo[_R](
                exec_at_timestamp=at_timestamp,
                func_id=self._func_id,
                task_id=task_id or uuid4().hex,
                timer_handler=time_handler,
                task_registered=self._task_registered,
            )
            self._task_info = task_info
        heapq.heappush(self._task_registered, task_info)
        return task_info

    def _set_result(
        self,
        task_or_func: asyncio.Future[_R] | Callable[..., _R],
        /,
    ) -> None:
        try:
            if isinstance(task_or_func, asyncio.Future):
                task = task_or_func
                result = task.result()
            else:
                func = task_or_func
                result = func()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._run_hooks_error(exc)
        else:
            self.task_info.result = result
            self._run_hooks_success(result)
        finally:
            _ = heapq.heappop(self._task_registered)
            self.task_info._event.set()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
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


class TaskExecutorSync(TaskExecutor[_R]):
    __slots__: tuple[str, ...] = (
        "_processpool_executor",
        "_threadpool_executor",
    )
    _func_injected: Callable[..., _R]
    _processpool_executor: concurrent.futures.ProcessPoolExecutor
    _threadpool_executor: concurrent.futures.ThreadPoolExecutor

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        func_injected: Callable[..., _R],
        task_registered: list[TaskInfo[_R]],
        tz: ZoneInfo,
    ) -> None:
        self._processpool_executor = concurrent.futures.ProcessPoolExecutor()
        self._threadpool_executor = concurrent.futures.ThreadPoolExecutor()
        super().__init__(
            loop=loop,
            func_id=func_id,
            task_registered=task_registered,
            func_injected=func_injected,
            tz=tz,
        )

    def __del__(self) -> None:
        self._processpool_executor.shutdown()
        self._threadpool_executor.shutdown()

    def _execute(self) -> None:
        if self._run_to_thread:
            future = self.loop.run_in_executor(
                self._threadpool_executor,
                self._func_injected,
            )
            future.add_done_callback(self._set_result)
        else:
            self._set_result(self._func_injected)

    def to_thread(self) -> TaskExecutor[_R]:
        self._run_to_thread: bool = True
        return self


class TaskExecutorAsync(TaskExecutor[_R]):
    _func_injected: Callable[..., Coroutine[None, None, _R]]

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        func_injected: Callable[..., Coroutine[None, None, _R]],
        task_registered: list[TaskInfo[_R]],
        tz: ZoneInfo,
    ) -> None:
        super().__init__(
            loop=loop,
            func_id=func_id,
            task_registered=task_registered,
            func_injected=func_injected,
            tz=tz,
        )

    def _execute(self) -> None:
        coro_task = asyncio.create_task(self._func_injected())
        coro_task.add_done_callback(self._set_result)

    def to_thread(self) -> TaskExecutorAsync[_R]:
        warnings.warn(
            "Method 'to_thread()' is ignored for async functions. "
            "Use it only with synchronous functions. "
            "Async functions are already executed in the event loop.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return self
