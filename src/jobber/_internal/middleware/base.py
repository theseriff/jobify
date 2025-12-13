from __future__ import annotations

import functools
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeVar, runtime_checkable

from jobber._internal.context import JobContext

CallNext = Callable[[JobContext], Awaitable[Any]]

ReturnT = TypeVar("ReturnT")


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
    async def target(context: JobContext) -> ReturnT:
        return await func(context)

    chain_of_middlewares = target
    for m in reversed(middleware):
        chain_of_middlewares = functools.partial(m, chain_of_middlewares)

    return chain_of_middlewares
