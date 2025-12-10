from __future__ import annotations

import functools
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeVar, runtime_checkable

from jobber._internal.context import JobContext
from jobber._internal.exceptions import JobSkippedError

CallNext = Callable[[JobContext], Awaitable[Any]]

_R = TypeVar("_R")


@runtime_checkable
class BaseMiddleware(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        pass


def build_middleware(
    middleware: Sequence[BaseMiddleware],
    /,
    func: Callable[..., Awaitable[_R]],
) -> CallNext:
    async def target(context: JobContext) -> _R:
        context.request_state.__has_called__ = True
        return await func(context)

    chain_of_middlewares = target
    for m in reversed(middleware):
        chain_of_middlewares = functools.partial(m, chain_of_middlewares)

    async def executor(context: JobContext) -> _R:
        result = await chain_of_middlewares(context)
        if "__has_called__" not in context.request_state:
            raise JobSkippedError
        return result

    return executor
