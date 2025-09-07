import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeGuard, TypeVar, overload

from taskaio._internal.taskplan.async_task import TaskPlanAsync
from taskaio._internal.taskplan.sync_task import TaskPlanSync

T = TypeVar("T")
P = ParamSpec("P")


def is_sync_callable(
    func: Callable[P, T | Coroutine[None, None, T]],
) -> TypeGuard[Callable[P, T]]:
    return not asyncio.iscoroutinefunction(func)


def is_async_callable(
    func: Callable[P, T | Coroutine[None, None, T]],
) -> TypeGuard[Callable[P, Coroutine[None, None, T]]]:
    return asyncio.iscoroutinefunction(func)


class TaskScheduler:
    _loop: asyncio.AbstractEventLoop

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_running_loop()
        self._tasks: list[TaskPlanSync[Any] | TaskPlanAsync[Any]] = []

    @overload
    def schedule(  # type: ignore[overload-overlap]
        self,
        func: Callable[P, Coroutine[None, None, T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> TaskPlanAsync[T]: ...

    @overload
    def schedule(
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> TaskPlanSync[T]: ...

    def schedule(
        self,
        func: Callable[P, T | Coroutine[None, None, T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> TaskPlanSync[T] | TaskPlanAsync[T]:
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
