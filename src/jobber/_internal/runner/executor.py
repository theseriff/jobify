import asyncio
from collections.abc import Callable
from typing import Generic, TypeVar, final

from jobber._internal.common.constants import ExecutionMode
from jobber._internal.context import JobContext, WorkerPools
from jobber._internal.injection import inject_context
from jobber._internal.runner.runnable import Runnable, iscoroutinerunnable

_R = TypeVar("_R")


@final
class Executor(Generic[_R]):
    __slots__: tuple[str, ...] = (
        "getloop",
        "worker_pools",
    )

    def __init__(
        self,
        *,
        worker_pools: WorkerPools,
        getloop: Callable[[], asyncio.AbstractEventLoop],
    ) -> None:
        self.worker_pools = worker_pools
        self.getloop = getloop

    async def __call__(self, context: JobContext) -> _R:
        runnable: Runnable[_R] = context.runnable
        exec_mode = runnable.exec_mode
        inject_context(runnable, context)

        if iscoroutinerunnable(runnable):
            return await runnable()

        getloop = self.getloop
        match exec_mode:
            case ExecutionMode.THREAD:
                threadpool = self.worker_pools.threadpool
                return await getloop().run_in_executor(threadpool, runnable)
            case ExecutionMode.PROCESS:
                processpool = self.worker_pools.processpool
                return await getloop().run_in_executor(processpool, runnable)
            case _:
                return runnable()
