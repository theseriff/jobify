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

from iojobs._internal.datastructures import State
from iojobs._internal.runner.job import Job

_ReturnType = TypeVar("_ReturnType")
CallNextChain = Callable[[Job[_ReturnType], State], Awaitable[_ReturnType]]


@runtime_checkable
class BaseMiddleware(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def __call__(
        self,
        call_next: CallNextChain[Any],
        job: Job[Any],
        state: State,
    ) -> Any: ...  # noqa: ANN401
