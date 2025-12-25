from __future__ import annotations

import functools
import inspect
import warnings
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Final, Generic, ParamSpec, TypeVar

from typing_extensions import override

from jobber._internal.common.constants import RunMode

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from concurrent.futures import Executor

    from jobber._internal.common.types import LoopFactory
    from jobber._internal.configuration import JobberConfiguration

ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")


class RunStrategy(ABC, Generic[ParamsT, ReturnT]):
    __slots__: tuple[str, ...] = ("func",)

    def __init__(self, func: Callable[ParamsT, ReturnT]) -> None:
        self.func: Final = func

    @abstractmethod
    async def __call__(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ReturnT:
        raise NotImplementedError


class SyncStrategy(RunStrategy[ParamsT, ReturnT]):
    @override
    async def __call__(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ReturnT:
        return self.func(*args, **kwargs)


class AsyncStrategy(RunStrategy[ParamsT, ReturnT]):
    @override
    async def __call__(
        self: AsyncStrategy[ParamsT, Awaitable[ReturnT]],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ReturnT:
        return await self.func(*args, **kwargs)


class PoolStrategy(RunStrategy[ParamsT, ReturnT]):
    __slots__: tuple[str, ...] = ("executor", "getloop")

    def __init__(
        self,
        func: Callable[ParamsT, ReturnT],
        executor: Executor | None,
        getloop: LoopFactory,
    ) -> None:
        super().__init__(func)
        self.executor: Executor | None = executor
        self.getloop: LoopFactory = getloop

    @override
    async def __call__(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ReturnT:
        func_call = functools.partial(self.func, *args, **kwargs)
        return await self.getloop().run_in_executor(self.executor, func_call)


class Runnable(Generic[ReturnT]):
    __slots__: tuple[str, ...] = ("bound", "strategy")

    def __init__(
        self,
        strategy: RunStrategy[ParamsT, ReturnT],
        bound: inspect.BoundArguments,
    ) -> None:
        self.strategy: Final = strategy
        self.bound: inspect.BoundArguments = bound

    def __call__(self) -> Awaitable[ReturnT]:
        return self.strategy(*self.bound.args, **self.bound.kwargs)


def _validate_run_mode(mode: RunMode | None, *, is_async: bool) -> RunMode:
    if is_async:
        if mode in (RunMode.PROCESS, RunMode.THREAD):
            msg = (
                "Async functions are always done in the main loop."
                " This mode (PROCESS/THREAD) is not used."
            )
            warnings.warn(msg, category=RuntimeWarning, stacklevel=3)
        return RunMode.MAIN
    if mode is None:
        return RunMode.THREAD
    return mode


def create_run_strategy(
    func: Callable[ParamsT, ReturnT],
    jobber_config: JobberConfiguration,
    *,
    mode: RunMode | None,
) -> RunStrategy[ParamsT, ReturnT]:
    # inspect.iscoroutinefunction returns TypeGuard,
    # but we need a regular bool variable
    is_async = bool(inspect.iscoroutinefunction(func))

    mode = _validate_run_mode(mode, is_async=is_async)
    if is_async:
        return AsyncStrategy(func)

    match mode:
        case RunMode.PROCESS:
            processpool = jobber_config.worker_pools.processpool
            return PoolStrategy(func, processpool, jobber_config.getloop)
        case RunMode.THREAD:
            threadpool = jobber_config.worker_pools.threadpool
            return PoolStrategy(func, threadpool, jobber_config.getloop)
        case _:
            return SyncStrategy(func)
