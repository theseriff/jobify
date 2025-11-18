import asyncio
import functools
from typing import Generic, TypeVar, cast, final

from jobber._internal.common.constants import ExecutionMode
from jobber._internal.context import JobberContext

_ReturnType = TypeVar("_ReturnType")


@final
class Executor(Generic[_ReturnType]):
    __slots__: tuple[str, ...] = (
        "execution_mode",
        "func_injected",
        "jobber_ctx",
    )

    def __init__(
        self,
        *,
        execution_mode: ExecutionMode,
        func_injected: functools.partial[_ReturnType],
        jobber_ctx: JobberContext,
    ) -> None:
        self.jobber_ctx = jobber_ctx
        self.func_injected = func_injected
        self.execution_mode = execution_mode

    async def __call__(self) -> _ReturnType:
        handler = self.func_injected
        if asyncio.iscoroutinefunction(handler):
            return cast("_ReturnType", await handler())
        match self.execution_mode:
            case ExecutionMode.THREAD:
                return await self.jobber_ctx.loop.run_in_executor(
                    self.jobber_ctx.executors.threadpool,
                    handler,
                )
            case ExecutionMode.PROCESS:
                return await self.jobber_ctx.loop.run_in_executor(
                    self.jobber_ctx.executors.processpool,
                    handler,
                )
            case _:
                return handler()
