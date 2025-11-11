import asyncio
import concurrent.futures
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar, final

_ReturnType = TypeVar("_ReturnType")
_Return_co = TypeVar("_Return_co", covariant=True)


class CommandRunner(Protocol[_Return_co], metaclass=ABCMeta):
    @abstractmethod
    async def run(self) -> _Return_co:
        raise NotImplementedError


@final
class SyncRunner(CommandRunner[_ReturnType]):
    __slots__: tuple[str, ...] = ("_original_func",)

    def __init__(self, original_func: Callable[..., _ReturnType]) -> None:
        self._original_func = original_func

    async def run(self) -> _ReturnType:
        return self._original_func()


@final
class AsyncRunner(CommandRunner[_ReturnType]):
    __slots__: tuple[str, ...] = ("_original_func",)

    def __init__(
        self,
        original_func: Callable[..., Awaitable[_ReturnType]],
    ) -> None:
        self._original_func = original_func

    async def run(self) -> _ReturnType:
        return await self._original_func()


@final
class ExecutorPoolRunner(CommandRunner[_ReturnType]):
    __slots__: tuple[str, ...] = ("_executor", "_loop", "_original_func")

    def __init__(
        self,
        original_func: Callable[..., _ReturnType],
        executor: concurrent.futures.Executor,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._original_func = original_func
        self._executor = executor
        self._loop = loop

    async def run(self) -> _ReturnType:
        return await self._loop.run_in_executor(
            self._executor,
            self._original_func,
        )
