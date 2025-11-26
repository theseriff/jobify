import asyncio
import functools
from collections.abc import Callable
from typing import Generic, TypeVar, cast, final

from jobber._internal.common.constants import ExecutionMode
from jobber._internal.context import JobContext, WorkerPools
from jobber._internal.injection import inject_context

_ReturnType = TypeVar("_ReturnType")


@final
class Executor(Generic[_ReturnType]):
    __slots__: tuple[str, ...] = (
        "exec_mode",
        "getloop",
        "runnable",
        "worker_pools",
    )

    def __init__(
        self,
        *,
        exec_mode: ExecutionMode,
        runnable: functools.partial[_ReturnType],
        worker_pools: WorkerPools,
        getloop: Callable[[], asyncio.AbstractEventLoop],
    ) -> None:
        self.exec_mode = exec_mode
        self.worker_pools = worker_pools
        self.runnable = runnable
        self.getloop = getloop

    async def __call__(self, context: JobContext) -> _ReturnType:
        handler = self.runnable
        inject_context(handler, context)
        if asyncio.iscoroutinefunction(handler):
            return cast("_ReturnType", await handler())

        loop = self.getloop()
        match self.exec_mode:
            case ExecutionMode.THREAD:
                threadpool = self.worker_pools.threadpool
                return await loop.run_in_executor(threadpool, handler)
            case ExecutionMode.PROCESS:
                processpool = self.worker_pools.processpool
                return await loop.run_in_executor(processpool, handler)
            case _:
                return handler()
