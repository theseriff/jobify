from __future__ import annotations

import asyncio
import warnings
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Protocol, TypeVar, cast, final

from jobber._internal.common.constants import ExecutionMode

if TYPE_CHECKING:
    import concurrent.futures
    from collections.abc import Awaitable

    from jobber._internal.context import JobberContext
    from jobber._internal.handler import Handler

_ReturnType = TypeVar("_ReturnType")
_Return_co = TypeVar("_Return_co", covariant=True)


class Executor(Protocol[_Return_co], metaclass=ABCMeta):
    @abstractmethod
    async def run(self) -> _Return_co:
        raise NotImplementedError


@final
class SyncExecutor(Executor[_ReturnType]):
    __slots__: tuple[str, ...] = ("_handler",)

    def __init__(self, handler: Handler[..., _ReturnType]) -> None:
        self._handler = handler

    async def run(self) -> _ReturnType:
        return self._handler()


@final
class AsyncExecutor(Executor[_ReturnType]):
    __slots__: tuple[str, ...] = ("_handler",)

    def __init__(
        self,
        handler: Handler[..., Awaitable[_ReturnType]],
    ) -> None:
        self._handler = handler

    async def run(self) -> _ReturnType:
        return await self._handler()


@final
class PoolExecutor(Executor[_ReturnType]):
    __slots__: tuple[str, ...] = ("_executor", "_handler", "_loop")

    def __init__(
        self,
        handler: Handler[..., _ReturnType],
        pool: concurrent.futures.Executor,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._handler = handler
        self._executor = pool
        self._loop = loop

    async def run(self) -> _ReturnType:
        return await self._loop.run_in_executor(self._executor, self._handler)


ASYNC_FUNC_EXECUTION_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""


def create_executor(
    handler: Handler[..., _ReturnType],
    exec_mode: ExecutionMode,
    jobber_ctx: JobberContext,
) -> Executor[_ReturnType]:
    if asyncio.iscoroutinefunction(handler.original_func):
        c = cast("Handler[..., Awaitable[_ReturnType]]", handler)
        executor = AsyncExecutor(c)
        if exec_mode is ExecutionMode.MAIN:
            return executor
        if exec_mode is ExecutionMode.PROCESS:
            warn = ASYNC_FUNC_EXECUTION_WARNING.format(fname="to_process")
        else:
            warn = ASYNC_FUNC_EXECUTION_WARNING.format(fname="to_thread")
        warnings.warn(warn, category=RuntimeWarning, stacklevel=2)
        return executor

    if exec_mode is ExecutionMode.MAIN:
        return SyncExecutor(handler)
    pool = (
        jobber_ctx.executors.processpool
        if exec_mode is ExecutionMode.PROCESS
        else jobber_ctx.executors.threadpool
    )
    loop = jobber_ctx.loop
    return PoolExecutor(handler, pool, loop)
