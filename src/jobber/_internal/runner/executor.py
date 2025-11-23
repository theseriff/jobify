import asyncio
import functools
from typing import Generic, TypeVar, final

from jobber._internal.common.constants import ExecutionMode
from jobber._internal.context import ExecutorsPool, JobContext
from jobber._internal.injection import inject_context

_ReturnType = TypeVar("_ReturnType")


@final
class Executor(Generic[_ReturnType]):
    __slots__: tuple[str, ...] = (
        "exec_mode",
        "exeutors_pool",
        "func_injected",
        "loop",
    )

    def __init__(
        self,
        *,
        exec_mode: ExecutionMode,
        func_injected: functools.partial[_ReturnType],
        executors_pool: ExecutorsPool,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.exec_mode = exec_mode
        self.exeutors_pool = executors_pool
        self.func_injected = func_injected
        self.loop = loop

    async def __call__(self, context: JobContext) -> _ReturnType:
        handler = self.func_injected
        inject_context(handler, context)
        if asyncio.iscoroutinefunction(handler):
            result: _ReturnType = await handler()
            return result
        match self.exec_mode:
            case ExecutionMode.THREAD:
                threadpool = self.exeutors_pool.threadpool
                return await self.loop.run_in_executor(threadpool, handler)
            case ExecutionMode.PROCESS:
                processpool = self.exeutors_pool.processpool
                return await self.loop.run_in_executor(processpool, handler)
            case _:
                return handler()
