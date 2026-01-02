from __future__ import annotations

import functools
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeVar, runtime_checkable

from jobify._internal.context import JobContext

ReturnT = TypeVar("ReturnT")
CallNext = Callable[[JobContext], Awaitable[Any]]


@runtime_checkable
class BaseMiddleware(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        pass


def build_middleware(
    middleware: Sequence[BaseMiddleware],
    /,
    func: Callable[[JobContext], Awaitable[ReturnT]],
) -> CallNext:
    chain_of_middlewares = func
    for m in reversed(middleware):
        chain_of_middlewares = functools.partial(m, chain_of_middlewares)

    return chain_of_middlewares
