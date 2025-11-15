from __future__ import annotations

import functools
from typing import TYPE_CHECKING, TypeVar, final

from iojobs._internal.exceptions import CallbackSkippedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from iojobs._internal.datastructures import State
    from iojobs._internal.middleware.base import BaseMiddleware, CallNextChain
    from iojobs._internal.runner.job import Job

_ReturnT = TypeVar("_ReturnT")


@final
class MiddlewareResolver:
    def __init__(
        self,
        middlewares: Sequence[BaseMiddleware] | None = None,
    ) -> None:
        self._middlewares = list(middlewares) if middlewares else []

    def add(self, *middlewares: BaseMiddleware) -> None:
        self._middlewares.extend(middlewares)

    def chain(
        self,
        callback: Callable[..., Awaitable[_ReturnT]],
        *,
        raise_if_skipped: bool = False,
    ) -> CallNextChain[_ReturnT]:
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
                raise CallbackSkippedError
            return result

        return executor
