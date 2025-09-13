from __future__ import annotations

import asyncio
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

from taskaio._internal.exceptions import LambdaNotAllowedError
from taskaio._internal.task_executor import (
    TaskExecutor,
    TaskExecutorAsync,
    TaskExecutorSync,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_P = ParamSpec("_P")
_R = TypeVar("_R")
FuncID = NewType("FuncID", str)


class FuncWrapper(Generic[_P, _R]):
    __slots__: tuple[str, ...] = (
        "_func_registered",
        "_loop",
        "task_scheduled",
    )

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop: Final = loop
        self._func_registered: dict[FuncID, Callable[_P, _R]] = {}
        self.task_scheduled: list[TaskExecutor[_R]] = []

    def register(
        self,
        func_id: str | None,
    ) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
        def wrapper(func: Callable[_P, _R]) -> Callable[_P, _R]:
            id_ = func_id or _create_func_id(func)
            self._func_registered[FuncID(id_)] = func

            @functools.wraps(func)
            def inner(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                func_injected = functools.partial(func, *args, **kwargs)

                _task: TaskExecutorAsync[_R] | TaskExecutorSync[_R]
                if asyncio.iscoroutinefunction(func_injected):
                    _task = TaskExecutorAsync(self._loop, func_injected)
                else:
                    _task = TaskExecutorSync(
                        self._loop,
                        cast("Callable[_P, _R]", func_injected),
                    )
                return func(*args, **kwargs)

            return inner

        return wrapper


def _create_func_id(func: Callable[_P, _R]) -> str:
    fname = func.__name__
    fmodule = func.__module__
    if fname == "<lambda>":
        raise LambdaNotAllowedError
    if fmodule == "__main__":
        fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
    return f"{fmodule}:{fname}"
