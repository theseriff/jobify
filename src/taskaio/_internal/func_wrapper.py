from __future__ import annotations

import asyncio
import functools
import os
import sys
from typing import (
    TYPE_CHECKING,
    Final,
    Generic,
    ParamSpec,
    TypeVar,
    cast,
)
from uuid import uuid4

from taskaio._internal._types import FuncID
from taskaio._internal.task_executor import (
    TaskExecutor,
    TaskExecutorAsync,
    TaskExecutorSync,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from taskaio._internal.task_executor import TaskInfo

_P = ParamSpec("_P")
_R = TypeVar("_R")


class FuncWrapper(Generic[_P, _R]):
    __slots__: tuple[str, ...] = (
        "_func_registered",
        "_loop",
        "task_registered",
    )

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop: Final = loop
        self._func_registered: dict[
            FuncID,
            Callable[_P, Coroutine[None, None, _R] | _R],
        ] = {}
        self.task_registered: list[TaskInfo[_R]] = []

    def register(
        self,
        func_id: str | None,
    ) -> Callable[[Callable[_P, _R]], Callable[_P, TaskExecutor[_R]]]:
        def wrapper(
            func: Callable[_P, Coroutine[None, None, _R] | _R],
        ) -> Callable[_P, TaskExecutor[_R]]:
            fn_id = FuncID(func_id or _create_func_id(func))
            self._func_registered[fn_id] = func

            @functools.wraps(func)
            def inner(*args: _P.args, **kwargs: _P.kwargs) -> TaskExecutor[_R]:
                task_exec: TaskExecutorAsync[_R] | TaskExecutorSync[_R]
                func_injected = functools.partial(func, *args, **kwargs)
                if asyncio.iscoroutinefunction(func_injected):
                    task_exec = TaskExecutorAsync(
                        loop=self._loop,
                        func_id=fn_id,
                        func_injected=func_injected,
                        task_registered=self.task_registered,
                    )
                else:
                    task_exec = TaskExecutorSync(
                        loop=self._loop,
                        func_id=fn_id,
                        func_injected=cast("Callable[_P, _R]", func_injected),
                        task_registered=self.task_registered,
                    )
                return task_exec

            return inner

        return wrapper


def _create_func_id(func: Callable[_P, _R]) -> str:
    fname = func.__name__
    fmodule = func.__module__
    if fname == "<lambda>":
        fname = f"lambda_{uuid4().hex}"
    if fmodule == "__main__":
        fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
    return f"{fmodule}:{fname}"
