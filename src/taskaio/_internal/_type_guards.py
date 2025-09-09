import asyncio
from collections.abc import Callable, Coroutine
from typing import ParamSpec, TypeGuard, TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")


def is_async_callable(
    func: Callable[_P, _R | Coroutine[None, None, _R]],
) -> TypeGuard[Callable[_P, Coroutine[None, None, _R]]]:
    return asyncio.iscoroutinefunction(func)
