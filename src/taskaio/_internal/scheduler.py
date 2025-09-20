from __future__ import annotations

from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, overload

from taskaio._internal._types import EMPTY
from taskaio._internal.func_wrapper import FuncWrapper

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from taskaio._internal.task_executor import TaskExecutor


_P = ParamSpec("_P")
_R = TypeVar("_R")


class TaskScheduler:
    __slots__: tuple[str, ...] = ("_wrapper",)

    def __init__(self, loop: asyncio.AbstractEventLoop = EMPTY) -> None:
        self._wrapper: FuncWrapper[..., Any] = FuncWrapper(  # pyright: ignore[reportExplicitAny]
            loop=loop,
        )

    @overload
    def register(
        self,
        func: Callable[_P, _R],
    ) -> Callable[_P, TaskExecutor[_R]]: ...

    @overload
    def register(
        self,
        *,
        func_id: str | None = None,
    ) -> Callable[[Callable[_P, _R]], Callable[_P, TaskExecutor[_R]]]: ...

    def register(
        self,
        func: Callable[_P, _R] | None = None,
        *,
        func_id: str | None = None,
    ) -> (
        Callable[_P, TaskExecutor[_R]]
        | Callable[[Callable[_P, _R]], Callable[_P, TaskExecutor[_R]]]
    ):
        wrapper = self._wrapper.register(func_id)
        if func is not None:
            return wrapper(func)
        return wrapper

    async def wait_for_complete(self) -> None:
        tasks_scheduled = self._wrapper.task_registered
        while tasks_scheduled:
            task = tasks_scheduled[0]
            await task.wait()
