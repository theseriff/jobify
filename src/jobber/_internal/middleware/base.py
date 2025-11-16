# pyright: reportExplicitAny=false
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from jobber._internal.common.datastructures import State
from jobber._internal.runner.job import Job

_ReturnType = TypeVar("_ReturnType")
CallNext = Callable[[Job[_ReturnType], State], Awaitable[_ReturnType]]


@runtime_checkable
class BaseMiddleware(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def __call__(
        self,
        call_next: CallNext[Any],
        job: Job[Any],
        state: State,
    ) -> Any: ...  # noqa: ANN401
