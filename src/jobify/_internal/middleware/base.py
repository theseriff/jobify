from __future__ import annotations

import functools
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Protocol,
    TypeAlias,
    TypeVar,
    runtime_checkable,
)

from jobify._internal.context import JobContext, OuterContext

if TYPE_CHECKING:
    import asyncio

ReturnT = TypeVar("ReturnT")
CallNext: TypeAlias = Callable[[JobContext], Awaitable[Any]]
OuterCallNext: TypeAlias = Callable[[OuterContext], Awaitable[Any]]


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


@runtime_checkable
class OuterMiddleware(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def __call__(
        self,
        call_next: OuterCallNext,
        context: OuterContext,
    ) -> Any:  # noqa: ANN401
        pass


def build_outer_middleware(
    middleware: Sequence[OuterMiddleware],
    /,
    func: Callable[[OuterContext], Awaitable[asyncio.Handle]],
) -> OuterCallNext:
    chain_of_middlewares = func
    for m in reversed(middleware):
        chain_of_middlewares = functools.partial(m, chain_of_middlewares)

    return chain_of_middlewares
