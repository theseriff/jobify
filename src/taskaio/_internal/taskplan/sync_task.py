import asyncio
import functools
from collections.abc import Callable
from typing import Final, ParamSpec, TypeVar

from .base import TaskPlan

_P = ParamSpec("_P")
_R = TypeVar("_R")


class TaskPlanSync(TaskPlan[_R]):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        func: Callable[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        super().__init__(loop, func, *args, **kwargs)
        self._func_injected: Final = functools.partial(
            func,
            *args,
            **kwargs,
        )
        self._run_in_thread: bool = False

    def _begin(self) -> None:
        if self._run_in_thread:
            coro_callback = asyncio.to_thread(self._func_injected)
            task = asyncio.create_task(coro_callback)
            task.add_done_callback(self._get_result)
        else:
            self._get_result(self._func_injected)

    def to_thread(self) -> None:
        self._run_in_thread = True
