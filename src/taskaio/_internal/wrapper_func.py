from __future__ import annotations

import functools
import os
import sys
from typing import (
    TYPE_CHECKING,
    Final,
    Generic,
    NewType,
    ParamSpec,
    TypeVar,
    cast,
)

from taskaio._internal._type_guards import is_async_callable
from taskaio._internal.exceptions import LambdaNotAllowedError
from taskaio._internal.task_plan import TaskPlan, TaskPlanAsync, TaskPlanSync

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

_P = ParamSpec("_P")
_R = TypeVar("_R")
FuncID = NewType("FuncID", str)


class WrapperFunc(Generic[_P, _R]):
    def __init__(
        self,
        *,
        origin_func: Callable[_P, _R],
        scheduled_tasks: list[TaskPlan[_R]],
        loop: asyncio.AbstractEventLoop,
        func_id: str | None,
    ) -> None:
        _ = functools.update_wrapper(self, origin_func)
        self._origin_func: Final = origin_func
        self._func_id: Final = func_id or self._create_func_id()
        self._loop: Final = loop
        self._task_scheduled: Final = scheduled_tasks

    @property
    def func_id(self) -> FuncID:
        return FuncID(self._func_id)

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        return self._origin_func(*args, **kwargs)

    def _create_func_id(self) -> str:
        func = self._origin_func
        fname = func.__name__
        fmodule = func.__module__
        if fname == "<lambda>":
            raise LambdaNotAllowedError
        if fmodule == "__main__":
            fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
        return f"{fmodule}:{fname}"

    def schedule(
        self,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> TaskPlanAsync[_R] | TaskPlanSync[_R]:
        func_injected = functools.partial(self._origin_func, *args, **kwargs)
        plan: TaskPlanAsync[_R] | TaskPlanSync[_R]
        if is_async_callable(func_injected):
            plan = TaskPlanAsync(self._loop, func_injected)
        else:
            plan = TaskPlanSync(
                self._loop,
                cast("Callable[_P, _R]", func_injected),
            )
        self._task_scheduled.append(plan)
        return plan
