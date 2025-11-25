from __future__ import annotations

import asyncio
import functools
import warnings
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)
from zoneinfo import ZoneInfo

from jobber._internal.common.constants import EMPTY, ExecutionMode
from jobber._internal.common.datastructures import State
from jobber._internal.context import AppContext, ExecutorsPool
from jobber._internal.durable.dummy import DummyRepository
from jobber._internal.durable.sqlite import SQLiteJobRepository
from jobber._internal.func_wrapper import FuncWrapper, create_default_name
from jobber._internal.middleware.base import MiddlewarePipeline
from jobber._internal.middleware.exceptions import ExceptionMiddleware
from jobber._internal.serializers.json import JSONSerializer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType

    from jobber._internal.common.types import (
        Lifespan,
        MappingExceptionHandlers,
    )
    from jobber._internal.durable.abc import JobRepository
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.job import Job
    from jobber._internal.serializers.abc import JobsSerializer


_FuncParams = ParamSpec("_FuncParams")
_ReturnType = TypeVar("_ReturnType")
_AppType = TypeVar("_AppType", bound="Jobber")


@asynccontextmanager
async def _lifespan_stub(_: Jobber) -> AsyncIterator[None]:
    yield None


class Jobber:
    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        durable: JobRepository | Literal[False] | None = None,
        lifespan: Lifespan[_AppType] | None = None,
        serializer: JobsSerializer | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
        exception_handlers: MappingExceptionHandlers | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
    ) -> None:
        if durable is False:
            durable = DummyRepository()
        elif durable is None:
            durable = SQLiteJobRepository()
        self._app_ctx: AppContext = AppContext(
            _loop=loop,
            tz=tz or ZoneInfo("UTC"),
            durable=durable,
            executors=ExecutorsPool(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            serializer=serializer or JSONSerializer(),
            asyncio_tasks=set(),
        )
        self._lifespan: AsyncIterator[None] = self._run_lifespan(
            lifespan or _lifespan_stub,
        )
        self._function_registry: dict[str, FuncWrapper[..., Any]] = {}
        self._job_registry: dict[str, Job[Any]] = {}
        user_exception_handlers = exception_handlers or {}
        self.exception_handler: ExceptionMiddleware = ExceptionMiddleware(
            {**user_exception_handlers},
            threadpool_executor,
            self._app_ctx.getloop,
        )
        user_middlewares = middleware or []
        self.middleware: MiddlewarePipeline = MiddlewarePipeline(
            [*user_middlewares, self.exception_handler]
        )
        self.state: State = State()

    @overload
    def register(
        self,
        func: Callable[_FuncParams, _ReturnType],
    ) -> FuncWrapper[_FuncParams, _ReturnType]: ...

    @overload
    def register(
        self,
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> Callable[
        [Callable[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]: ...

    @overload
    def register(
        self,
        func: Callable[_FuncParams, _ReturnType],
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> FuncWrapper[_FuncParams, _ReturnType]: ...

    def register(
        self,
        func: Callable[_FuncParams, _ReturnType] | None = None,
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> (
        FuncWrapper[_FuncParams, _ReturnType]
        | Callable[
            [Callable[_FuncParams, _ReturnType]],
            FuncWrapper[_FuncParams, _ReturnType],
        ]
    ):
        wrapper = self._register(job_name=job_name, exec_mode=exec_mode)
        if callable(func):
            return wrapper(func)
        return wrapper  # pragma: no cover

    def _register(
        self,
        *,
        job_name: str | None,
        exec_mode: ExecutionMode,
    ) -> Callable[
        [Callable[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]:
        def wrapper(
            func: Callable[_FuncParams, _ReturnType],
        ) -> FuncWrapper[_FuncParams, _ReturnType]:
            nonlocal exec_mode

            is_async = asyncio.iscoroutinefunction(func)
            if is_async:
                if exec_mode in (ExecutionMode.PROCESS, ExecutionMode.THREAD):
                    msg = (
                        "Async functions are always done in the main loop."
                        " This mode (PROCESS/THREAD) is not used."
                    )
                    warnings.warn(msg, category=RuntimeWarning, stacklevel=3)
                exec_mode = ExecutionMode.MAIN
            elif exec_mode is EMPTY:
                exec_mode = ExecutionMode.THREAD

            fname = job_name or create_default_name(func)
            if fwrapper := self._function_registry.get(fname):
                return cast("FuncWrapper[_FuncParams, _ReturnType]", fwrapper)

            fwrapper = FuncWrapper(
                state=self.state,
                job_name=fname,
                app_context=self._app_ctx,
                original_func=func,
                job_registry=self._job_registry,
                exec_mode=exec_mode,
                middleware=self.middleware,
            )
            _ = functools.update_wrapper(fwrapper, func)
            self._function_registry[fname] = fwrapper
            return fwrapper

        return wrapper

    async def _run_lifespan(
        self,
        user_lifespan: Lifespan[Any],
    ) -> AsyncIterator[None]:
        async with user_lifespan(self) as maybe_state:
            if maybe_state is not None:
                self.state.update(maybe_state)
            yield None

    async def __aenter__(self) -> Jobber:
        await self.startup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        await self.shutdown()

    async def startup(self) -> None:
        await anext(self._lifespan)

    async def shutdown(self) -> None:
        self._app_ctx.close()
        await anext(self._lifespan, None)
