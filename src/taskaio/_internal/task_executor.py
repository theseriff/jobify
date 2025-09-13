from __future__ import annotations

import asyncio
import traceback
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Final, Generic, TypeVar
from uuid import uuid4

from taskaio._internal._types import EMPTY
from taskaio._internal.exceptions import (
    NegativeDelayError,
    TaskNotCompletedError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

_R = TypeVar("_R")


class TaskInfo(Generic[_R], ABC):
    __slots__: tuple[str, ...] = (
        "_event",
        "_on_error_callback",
        "_on_success_callback",
        "_result",
        "delay_seconds",
        "func_id",
        "task_id",
        "timer_handler",
    )

    def __init__(
        self,
        *,
        tm: asyncio.TimerHandle,
        task_id: str,
        delay_seconds: float,
        func_id: str,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._on_success_callback: list[Callable[[_R], None]] = []
        self._on_error_callback: list[Callable[[Exception], None]] = []
        self._result: _R = EMPTY
        self.timer_handler: asyncio.TimerHandle = tm
        self.func_id: str = func_id
        self.task_id: str = task_id
        self.delay_seconds: float = delay_seconds

    @property
    def result(self) -> _R:
        if self._result is EMPTY:
            raise TaskNotCompletedError
        return self._result

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

    def _set_result(
        self,
        task: asyncio.Task[_R] | Callable[..., _R],
        /,
    ) -> None:
        try:
            if isinstance(task, asyncio.Task):
                result = task.result()
            else:
                result = task()
        except Exception as exc:  # noqa: BLE001
            self._run_hooks_error(exc)
        else:
            self._result = result
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


class TaskBuilder(Generic[_R], ABC):
    __slots__: tuple[str, ...] = (
        "_event",
        "_func_id",
        "_loop",
        "_on_error_callback",
        "_on_success_callback",
    )

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        func_id: str,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._func_id: str = func_id
        self._loop: asyncio.AbstractEventLoop = (
            loop or asyncio.get_running_loop()
        )
        self._on_success_callback: list[Callable[[_R], None]] = []
        self._on_error_callback: list[Callable[[Exception], None]] = []

    @abstractmethod
    def _execute(self) -> None:
        raise NotImplementedError

    def at(self, at: datetime, /) -> TaskInfo[_R]:
        timestamp_now = datetime.now(tz=at.tzinfo).timestamp()
        timestamp_at = at.timestamp()
        delay_seconds = timestamp_at - timestamp_now
        return self.delay(delay_seconds)

    def delay(self, delay_seconds: float, /) -> TaskInfo[_R]:
        if delay_seconds < 0:
            raise NegativeDelayError(delay_seconds)

        timer_handler = self._loop.call_later(
            delay_seconds,
            self._execute,
        )
        return TaskInfo(
            tm=timer_handler,
            task_id="1",
            delay_seconds=delay_seconds,
            func_id="1",
        )

    def on_success(self, *callbacks: Callable[[_R], None]) -> TaskBuilder[_R]:
        self._on_success_callback.extend(callbacks)
        return self

    def on_error(
        self,
        *callbacks: Callable[[Exception], None],
    ) -> TaskBuilder[_R]:
        self._on_error_callback.extend(callbacks)
        return self


class TaskExecutor(Generic[_R], ABC):
    __slots__: tuple[str, ...] = (
        "_event",
        "_loop",
        "_on_error_callback",
        "_on_success_callback",
        "_result",
        "_task_id",
        "_timer_handler",
        "delay_seconds",
        "is_planned",
    )

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop = loop
        self._on_success_callback: list[Callable[[_R], None]] = []
        self._on_error_callback: list[Callable[[Exception], None]] = []
        self._result: _R = EMPTY
        self._timer_handler: asyncio.TimerHandle = EMPTY
        self._task_id: str = EMPTY
        self.delay_seconds: float = 0
        self.is_planned: bool = False

    @abstractmethod
    def _execute(self) -> None:
        raise NotImplementedError

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is EMPTY:
            self._loop = asyncio.get_running_loop()
        return self._loop

    @property
    def task_id(self) -> str:
        return self._task_id or uuid4().hex

    @property
    def result(self) -> _R:
        if self._result is EMPTY:
            raise TaskNotCompletedError
        return self._result

    def at(self, at: datetime, /) -> TaskExecutor[_R]:
        timestamp_now = datetime.now(tz=at.tzinfo).timestamp()
        timestamp_at = at.timestamp()
        delay_seconds = timestamp_at - timestamp_now
        return self.delay(delay_seconds)

    def delay(self, delay_seconds: float, /) -> TaskExecutor[_R]:
        self.delay_seconds = delay_seconds
        if delay_seconds < 0:
            warnings.warn(
                f"Negative delay_seconds ({delay_seconds}) is not supported; "
                "using 0 instead. Please provide non-negative values.",
                UserWarning,
                stacklevel=2,
            )
        else:
            timer_handler = self.loop.call_later(
                self.delay_seconds,
                self._execute,
            )
            self._timer_handler = timer_handler
            self.is_planned = True
        return self

    def is_done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        if not self.is_planned:
            warnings.warn(
                "Cannot wait for unplanned task. "
                "Call at(..) or delay(..) first.",
                category=RuntimeWarning,
                stacklevel=2,
            )
        elif self.is_done():
            warnings.warn(
                "Task is already done - waiting for completion is unnecessary",
                category=RuntimeWarning,
                stacklevel=2,
            )
        else:
            _ = await self._event.wait()

    def on_success(self, *callbacks: Callable[[_R], None]) -> TaskExecutor[_R]:
        self._on_success_callback.extend(callbacks)
        return self

    def on_error(
        self,
        *callbacks: Callable[[Exception], None],
    ) -> TaskExecutor[_R]:
        self._on_error_callback.extend(callbacks)
        return self

    def _set_result(
        self,
        task: asyncio.Task[_R] | Callable[..., _R],
        /,
    ) -> None:
        try:
            if isinstance(task, asyncio.Task):
                result = task.result()
            else:
                result = task()
        except Exception as exc:  # noqa: BLE001
            self._run_hooks_error(exc)
        else:
            self._result = result
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


class TaskExecutorSync(TaskExecutor[_R]):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        func_injected: Callable[..., _R],
    ) -> None:
        super().__init__(loop)
        self._func_injected: Final = func_injected
        self._run_in_thread: bool = False

    def _execute(self) -> None:
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
        loop: asyncio.AbstractEventLoop,
        func: Callable[..., Coroutine[None, None, _R]],
    ) -> None:
        super().__init__(loop)
        self._func_injected: Final = func

    def _execute(self) -> None:
        coro_task = asyncio.create_task(self._func_injected())
        coro_task.add_done_callback(self._set_result)
