from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeAlias, TypeVar

from jobify._internal.context import JobContext, OuterContext

ReturnT = TypeVar("ReturnT")
CallNext: TypeAlias = Callable[[JobContext], Awaitable[Any]]
CallNextOuter: TypeAlias = Callable[[OuterContext], Awaitable[asyncio.Handle]]


class BaseMiddleware(Protocol):
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


class BaseOuterMiddleware(Protocol):
    async def __call__(self, call_next: CallNextOuter, context: OuterContext) -> Any:  # noqa: ANN401
        pass


def build_outer_middleware(
    middleware: Sequence[BaseOuterMiddleware],
    /,
    func: Callable[[OuterContext], Awaitable[asyncio.Handle]],
) -> CallNextOuter:
    chain_of_middlewares = func
    for m in reversed(middleware):
        chain_of_middlewares = functools.partial(m, chain_of_middlewares)

    return chain_of_middlewares
