from __future__ import annotations

import functools
import os
import sys
from typing import (
    TYPE_CHECKING,
    Final,
    Generic,
    ParamSpec,
    TypeVar,
)

from taskaio._internal._types import FuncID
from taskaio._internal.exceptions import LambdaNotAllowedError

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from taskaio._internal.task_executor import (
        TaskInfo,
    )

_P = ParamSpec("_P")
_R = TypeVar("_R")


class FuncWrapper(Generic[_P, _R]):
    __slots__: tuple[str, ...] = (
        "_func_registered",
        "_loop",
        "task_scheduled",
    )

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop: Final = loop
        self._func_registered: dict[FuncID, Callable[_P, _R]] = {}
        self.task_scheduled: list[TaskInfo[_R]] = []

    def register(
        self,
        func_id: str | None,
    ) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
        def wrapper(func: Callable[_P, _R]) -> Callable[_P, _R]:
            id_ = func_id or _create_func_id(func)
            self._func_registered[FuncID(id_)] = func

            @functools.wraps(func)
            def inner(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                # func_injected = functools.partial(func, *args, **kwargs)  # noqa: E501, ERA001

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
