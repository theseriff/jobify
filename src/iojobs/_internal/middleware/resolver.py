from __future__ import annotations

import functools
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from iojobs._internal.datastructures import State
    from iojobs._internal.func_original import Callback
    from iojobs._internal.middleware.base import BaseMiddleware, CallNextChain
    from iojobs._internal.runner.job import Job

_ReturnT = TypeVar("_ReturnT")


class MiddlewareResolver:
    def __init__(
        self,
        middlewares: list[BaseMiddleware] | None = None,
    ) -> None:
        self._middlewares: list[BaseMiddleware] = middlewares or []

    def add_middleware(self, m: BaseMiddleware, /) -> None:
        self._middlewares.append(m)

    def chain_middlewares(
        self,
        callback: Callback[..., Awaitable[_ReturnT]],
    ) -> CallNextChain[_ReturnT]:
        def wrapper(_job: Job[_ReturnT], _state: State) -> Awaitable[_ReturnT]:
            return callback()

        chain_of_middlewares = wrapper
        for m in reversed(self._middlewares):
            chain_of_middlewares = functools.partial(m, chain_of_middlewares)

        return chain_of_middlewares
