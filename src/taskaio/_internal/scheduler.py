import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeGuard, TypeVar, overload

from taskaio._internal.taskplan.async_task import TaskPlanAsync
from taskaio._internal.taskplan.sync_task import TaskPlanSync

_P = ParamSpec("_P")
_R = TypeVar("_R")


def is_sync_callable(
    func: Callable[_P, _R | Coroutine[None, None, _R]],
) -> TypeGuard[Callable[_P, _R]]:
    return not asyncio.iscoroutinefunction(func)


def is_async_callable(
    func: Callable[_P, _R | Coroutine[None, None, _R]],
) -> TypeGuard[Callable[_P, Coroutine[None, None, _R]]]:
    return asyncio.iscoroutinefunction(func)


class TaskScheduler:
    _loop: asyncio.AbstractEventLoop

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_running_loop()
        self._tasks: list[TaskPlanSync[Any] | TaskPlanAsync[Any]] = []  # pyright: ignore[reportExplicitAny]

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
        self._tasks.sort(key=lambda t: t.delay_seconds, reverse=True)
        while self._tasks:
            task = self._tasks.pop()
            await task.wait()
