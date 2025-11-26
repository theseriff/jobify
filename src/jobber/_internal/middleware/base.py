# pyright: reportExplicitAny=false
from __future__ import annotations

import functools
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from typing import (
    TYPE_CHECKING,
    Any,
    Protocol,
    TypeVar,
    final,
    runtime_checkable,
)

from jobber._internal.context import JobContext
from jobber._internal.exceptions import HandlerSkippedError

if TYPE_CHECKING:
    from collections import deque

CallNext = Callable[[JobContext], Awaitable[Any]]

_ReturnT = TypeVar("_ReturnT")


@runtime_checkable
class BaseMiddleware(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        pass


@final
class MiddlewarePipeline:
    def __init__(
        self,
        middlewares: deque[BaseMiddleware],
        *,
        raise_if_skipped: bool = True,
    ) -> None:
        self._middlewares = middlewares
        self._error_if_skipped = raise_if_skipped

    def build_chain(
        self,
        callback: Callable[..., Awaitable[_ReturnT]],
    ) -> CallNext:
        async def target(context: JobContext) -> _ReturnT:
            context.request_state.__has_called__ = True
            return await callback(context)

        chain_of_middlewares = target
        for m in reversed(self._middlewares):
            chain_of_middlewares = functools.partial(m, chain_of_middlewares)

        async def executor(context: JobContext) -> _ReturnT:
            result = await chain_of_middlewares(context)
            self._raise_if_skipped(context)
            return result

        return executor

    def _raise_if_skipped(self, context: JobContext) -> None:
        has_called = getattr(context.request_state, "__has_called__", False)
        if self._error_if_skipped is True and has_called is False:
            raise HandlerSkippedError
