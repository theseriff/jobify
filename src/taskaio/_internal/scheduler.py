import asyncio
import os
import sys
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar, overload
from uuid import uuid4

from taskaio._internal._type_guards import is_async_callable, is_sync_callable
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
            loop or asyncio.get_running_loop()
        )

    def register(self, func: Callable[_P, _R]) -> None:
        self._register(func)

    def _register(self, func: Callable[_P, _R]) -> None:
        fmodule = func.__module__
        fname = func.__name__
        if fmodule == "__main__":
            fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
        if fname == "<lambda>":
            fname = f"lambda_{uuid4().hex}"
        callback_id = f"{fmodule}:{fname}"
        self._callback_registry[callback_id] = func

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
        if is_async_callable(func):
            return TaskPlanAsync(self._loop, func, *args, **kwargs)

        if is_sync_callable(func):
            return TaskPlanSync(self._loop, func, *args, **kwargs)

        err_msg = f"Unsupported function type: {type(func)}"
        raise TypeError(err_msg)

    async def wait_for_complete(self) -> None:
        self._scheduled_tasks.sort(key=lambda t: t.delay_seconds, reverse=True)
        while self._scheduled_tasks:
            task = self._scheduled_tasks.pop()
            await task.wait()
