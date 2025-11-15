from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Protocol, TypeVar, final

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    from collections.abc import Awaitable

    from iojobs._internal.func_original import Callback

_ReturnType = TypeVar("_ReturnType")
_Return_co = TypeVar("_Return_co", covariant=True)


class Runner(Protocol[_Return_co], metaclass=ABCMeta):
    @abstractmethod
    async def run(self) -> _Return_co:
        raise NotImplementedError


@final
class SyncRunner(Runner[_ReturnType]):
    __slots__: tuple[str, ...] = ("_callback",)

    def __init__(self, callback: Callback[..., _ReturnType]) -> None:
        self._callback = callback

    async def run(self) -> _ReturnType:
        return self._callback()


@final
class AsyncRunner(Runner[_ReturnType]):
    __slots__: tuple[str, ...] = ("_callback",)

    def __init__(
        self,
        callback: Callback[..., Awaitable[_ReturnType]],
    ) -> None:
        self._callback = callback

    async def run(self) -> _ReturnType:
        return await self._callback()


@final
class ExecutorPoolRunner(Runner[_ReturnType]):
    __slots__: tuple[str, ...] = ("_callback", "_executor", "_loop")

    def __init__(
        self,
        callback: Callback[..., _ReturnType],
        executor: concurrent.futures.Executor,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._callback = callback
        self._executor = executor
        self._loop = loop

    async def run(self) -> _ReturnType:
        return await self._loop.run_in_executor(self._executor, self._callback)
