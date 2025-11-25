# pyright: reportExplicitAny=false
from __future__ import annotations

import functools
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from typing import (
    Any,
    Protocol,
    TypeVar,
    final,
    runtime_checkable,
)

from jobber._internal.context import JobContext
from jobber._internal.exceptions import HandlerSkippedError

CallNext = Callable[[JobContext], Awaitable[Any]]

_ReturnT = TypeVar("_ReturnT")


@runtime_checkable
class BaseMiddleware(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        pass


@final
class MiddlewarePipeline:
    def __init__(self, middlewares: list[BaseMiddleware]) -> None:
        self._middlewares = middlewares

    def compose(
        self,
        callback: Callable[..., Awaitable[_ReturnT]],
        *,
        raise_if_skipped: bool = True,
    ) -> CallNext:
        has_called = False

        async def target(context: JobContext) -> _ReturnT:
            nonlocal has_called
            has_called = True
            return await callback(context)

        chain_of_middlewares = target
        for m in reversed(self._middlewares):
            chain_of_middlewares = functools.partial(m, chain_of_middlewares)

        async def executor(context: JobContext) -> _ReturnT:
            result = await chain_of_middlewares(context)
            if raise_if_skipped is True and has_called is False:
                raise HandlerSkippedError
            return result

        return executor
