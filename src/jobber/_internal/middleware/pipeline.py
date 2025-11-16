from __future__ import annotations

import functools
from typing import TYPE_CHECKING, TypeVar, final

from jobber._internal.exceptions import HandlerSkippedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from jobber._internal.datastructures import State
    from jobber._internal.middleware.base import BaseMiddleware, CallNext
    from jobber._internal.runner.job import Job

_ReturnT = TypeVar("_ReturnT")


@final
class MiddlewarePipeline:
    def __init__(
        self,
        middlewares: Sequence[BaseMiddleware] | None = None,
    ) -> None:
        self._middlewares = list(middlewares) if middlewares else []

    def use(self, *middlewares: BaseMiddleware) -> None:
        self._middlewares.extend(middlewares)

    def compose(
        self,
        callback: Callable[..., Awaitable[_ReturnT]],
        *,
        raise_if_skipped: bool = False,
    ) -> CallNext[_ReturnT]:
        has_called = False

        def target(_job: Job[_ReturnT], _state: State) -> Awaitable[_ReturnT]:
            nonlocal has_called
            has_called = True
            return callback()

        chain_of_middlewares = target
        for m in reversed(self._middlewares):
            chain_of_middlewares = functools.partial(m, chain_of_middlewares)

        async def executor(_job: Job[_ReturnT], state: State) -> _ReturnT:
            result = await chain_of_middlewares(_job, state)
            if raise_if_skipped is True and has_called is False:
                raise HandlerSkippedError
            return result

        return executor
