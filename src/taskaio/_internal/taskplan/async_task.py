import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Final, ParamSpec, TypeVar

from .base import TaskPlan

_P = ParamSpec("_P")
_R = TypeVar("_R")


class TaskPlanAsync(TaskPlan[_R]):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        func: Callable[_P, Coroutine[None, None, _R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        super().__init__(loop, func, *args, **kwargs)
        self._func_injected: Final = functools.partial(
            func,
            *args,
            **kwargs,
        )

    def _begin(self) -> None:
        task = asyncio.create_task(self._func_injected())
        task.add_done_callback(self._get_result)
