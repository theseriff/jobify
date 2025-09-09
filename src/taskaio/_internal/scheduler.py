from __future__ import annotations

from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from taskaio._internal._types import EMPTY
from taskaio._internal.wrapper_func import FuncID, WrapperFunc

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from taskaio._internal.task_plan import TaskPlan


_P = ParamSpec("_P")
_R = TypeVar("_R")


class TaskScheduler:
    __slots__: tuple[str, ...] = (
        "_func_registry",
        "_is_planning",
        "_loop",
        "_scheduled_tasks",
    )

    def __init__(self, loop: asyncio.AbstractEventLoop = EMPTY) -> None:
        self._func_registry: dict[
            FuncID,
            WrapperFunc[..., Any],  # pyright: ignore[reportExplicitAny]
        ] = {}
        self._is_planning: bool = False
        self._loop: asyncio.AbstractEventLoop = loop
        self._scheduled_tasks: list[TaskPlan[Any]] = []  # pyright: ignore[reportExplicitAny]

    def register(
        self,
        func: Callable[_P, _R],
        *,
        func_id: str | None = None,
    ) -> WrapperFunc[_P, _R]:
        wrapper_func = WrapperFunc(
            origin_func=func,
            scheduled_tasks=self._scheduled_tasks,
            loop=self._loop,
            func_id=func_id,
        )
        self._register(wrapper_func)
        return wrapper_func

    def _register(self, func: WrapperFunc[_P, _R]) -> None:
        self._func_registry[func.func_id] = func

    async def wait_for_complete(self) -> None:
        tasks = self._scheduled_tasks
        tasks.sort(key=lambda t: t.delay_seconds, reverse=True)
        while tasks:
            task = tasks.pop()
            await task.wait()
