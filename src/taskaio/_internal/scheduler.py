import asyncio
import contextlib
import functools
import os
import sys
import warnings
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar, cast, overload

from taskaio._internal._type_guards import is_async_callable
from taskaio._internal.exceptions import LambdaNotAllowedError
from taskaio._internal.taskplan.async_task import TaskPlanAsync
from taskaio._internal.taskplan.sync_task import TaskPlanSync

_P = ParamSpec("_P")
_R = TypeVar("_R")


class TaskScheduler:
    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._callback_registry: dict[str, Callable[..., Any]] = {}  # pyright: ignore[reportExplicitAny]
        self._scheduled_tasks: list[
            TaskPlanSync[Any] | TaskPlanAsync[Any]  # pyright: ignore[reportExplicitAny]
        ] = []
        self._loop: asyncio.AbstractEventLoop = (
            loop or self._get_running_loop() or self._create_new_event_loop()
        )

    def _get_running_loop(self) -> asyncio.AbstractEventLoop | None:
        with contextlib.suppress(RuntimeError):
            return asyncio.get_running_loop()
        return None

    def _create_new_event_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

    def register(self, callback: Callable[_P, _R]) -> Callable[_P, _R]:
        self._register(callback)

        @functools.wraps(callback)
        def inner(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return callback(*args, **kwargs)

        return inner

    def register_all(self, *callbacks: Callable[_P, _R]) -> None:
        for callback in callbacks:
            self._register(callback)

    def _register(
        self,
        func: Callable[_P, _R],
        *,
        callback_id: str | None = None,
    ) -> None:
        callback_id = callback_id or self._get_callback_id(func)
        self._callback_registry[callback_id] = func

    def _get_callback_id(self, func: Callable[_P, _R]) -> str:
        fname = func.__name__
        fmodule = func.__module__
        if fname == "<lambda>":
            raise LambdaNotAllowedError
        if fmodule == "__main__":
            fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
        return f"{fmodule}:{fname}"

    @overload
    def schedule(  # type: ignore[overload-overlap]
        self,
        func: Callable[_P, Coroutine[None, None, _R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> TaskPlanAsync[_R]: ...

    @overload
    def schedule(
        self,
        func: Callable[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> TaskPlanSync[_R]: ...

    def schedule(
        self,
        func: Callable[_P, _R | Coroutine[None, None, _R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> TaskPlanSync[_R] | TaskPlanAsync[_R]:
        callback_id = self._get_callback_id(func)
        if callback_id not in self._callback_registry:
            self._register(func, callback_id=callback_id)
            warnings.warn(
                f"Function {func.__name__!r} from module {func.__module__!r} "
                f"was not pre-registered. It has been automatically registered"
                f" with ID: {callback_id}. For better control and explicit "
                "registration, please use the register() method"
                "before scheduling tasks.",
                UserWarning,
                stacklevel=2,
            )

        task_plan: TaskPlanAsync[_R] | TaskPlanSync[_R]
        if is_async_callable(func):
            task_plan = TaskPlanAsync(self._loop, func, *args, **kwargs)
        else:
            func = cast("Callable[_P, _R]", func)
            task_plan = TaskPlanSync(self._loop, func, *args, **kwargs)
        self._scheduled_tasks.append(task_plan)
        return task_plan

    async def wait_for_complete(self) -> None:
        self._scheduled_tasks.sort(key=lambda t: t.delay_seconds, reverse=True)
        while self._scheduled_tasks:
            task = self._scheduled_tasks.pop()
            await task.wait()
