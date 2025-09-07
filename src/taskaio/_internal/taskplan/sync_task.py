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

    def _begin(self) -> None:
        try:
            self._result: _R = self._func_injected()
        finally:
            self._event.set()
