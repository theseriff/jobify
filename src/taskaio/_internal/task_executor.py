from __future__ import annotations

import asyncio
import traceback
import warnings
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Final, Generic, TypeVar
from uuid import uuid4

from taskaio._internal._types import EMPTY, FuncID
from taskaio._internal.exceptions import (
    NegativeDelayError,
    TaskNotCompletedError,
    TaskNotInitializedError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

_R = TypeVar("_R")


class TaskInfo(Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_result",
        "at_timestamp",
        "func_id",
        "task_id",
        "timer_handler",
    )

    def __init__(
        self,
        *,
        task_id: str,
        at_timestamp: float,
        func_id: str,
        timer_handler: asyncio.TimerHandle,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._result: _R = EMPTY
        self.at_timestamp: float = at_timestamp
        self.func_id: str = func_id
        self.task_id: str = task_id
        self.timer_handler: Final = timer_handler

    def is_done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        if self.is_done():
            warnings.warn(
                "Task is already done - waiting for completion is unnecessary",
                category=RuntimeWarning,
                stacklevel=2,
            )
        else:
            _ = await self._event.wait()

    @property
    def result(self) -> _R:
        if self._result is EMPTY:
            raise TaskNotCompletedError
        return self._result


class TaskExecutor(Generic[_R], ABC):
    __slots__: tuple[str, ...] = (
        "_event",
        "_func_id",
        "_loop",
        "_on_error_callback",
        "_on_success_callback",
        "_task_info",
    )

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._func_id: FuncID = func_id
        self._loop: asyncio.AbstractEventLoop = loop
        self._on_success_callback: list[Callable[[_R], None]] = []
        self._on_error_callback: list[Callable[[Exception], None]] = []
        self._task_info: TaskInfo[_R] | None = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is EMPTY:
            self._loop = asyncio.get_running_loop()
        return self._loop

    @abstractmethod
    def execute(self) -> None:
        raise NotImplementedError

    def delay(
        self,
        delay_seconds: float,
        /,
        task_id: str = EMPTY,
    ) -> TaskInfo[_R]:
        now = datetime.now(tz=timezone.utc)
        at = now + timedelta(seconds=delay_seconds)
        return self._at_execute(now=now, at=at, task_id=task_id)

    def at(self, at: datetime, /, *, task_id: str = EMPTY) -> TaskInfo[_R]:
        now = datetime.now(tz=at.tzinfo)
        return self._at_execute(now=now, at=at, task_id=task_id)

    def _at_execute(
        self,
        *,
        now: datetime,
        at: datetime,
        task_id: str,
    ) -> TaskInfo[_R]:
        now_timestamp = now.timestamp()
        at_timestamp = at.timestamp()
        delay_seconds = at_timestamp - now_timestamp
        if delay_seconds < 0:
            raise NegativeDelayError(delay_seconds)
        when = self.loop.time() + delay_seconds
        time_handler = self.loop.call_at(when, self.execute)
        task_info = TaskInfo[_R](
            at_timestamp=at_timestamp,
            func_id=self._func_id,
            task_id=task_id or uuid4().hex,
            timer_handler=time_handler,
        )
        self._task_info = task_info
        return task_info

    @property
    def task_info(self) -> TaskInfo[_R]:
        if self._task_info is None:
            raise TaskNotInitializedError
        return self._task_info

    def _set_result(
        self,
        task_or_func: asyncio.Task[_R] | Callable[..., _R],
        /,
    ) -> None:
        try:
            if isinstance(task_or_func, asyncio.Task):
                task = task_or_func
                result = task.result()
            else:
                func = task_or_func
                result = func()
        except Exception as exc:  # noqa: BLE001
            self._run_hooks_error(exc)
        else:
            self.task_info._result = result  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
            self._run_hooks_success(result)
        finally:
            self._event.set()

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

    def on_success(
        self,
        *callbacks: Callable[[_R], None],
    ) -> TaskExecutor[_R]:
        self._on_success_callback.extend(callbacks)
        return self

    def on_error(
        self,
        *callbacks: Callable[[Exception], None],
    ) -> TaskExecutor[_R]:
        self._on_error_callback.extend(callbacks)
        return self


class TaskExecutorSync(TaskExecutor[_R]):
    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        func_injected: Callable[..., _R],
    ) -> None:
        super().__init__(loop=loop, func_id=func_id)
        self._func_injected: Final = func_injected
        self._run_in_thread: bool = False

    def execute(self) -> None:
        if self._run_in_thread:
            coro_callback = asyncio.to_thread(self._func_injected)
            coro_task = asyncio.create_task(coro_callback)
            coro_task.add_done_callback(self._set_result)
        else:
            self._set_result(self._func_injected)

    def to_thread(self) -> None:
        self._run_in_thread = True


class TaskExecutorAsync(TaskExecutor[_R]):
    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: FuncID,
        _func_injected: Callable[..., Coroutine[None, None, _R]],
    ) -> None:
        super().__init__(loop=loop, func_id=func_id)
        self._func_injected: Final = _func_injected

    def execute(self) -> None:
        coro_task = asyncio.create_task(self._func_injected())
        coro_task.add_done_callback(self._set_result)
