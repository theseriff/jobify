from __future__ import annotations

import functools
from collections import deque
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    ParamSpec,
    TypeVar,
    cast,
    final,
    overload,
)
from zoneinfo import ZoneInfo

from jobber._internal.common.constants import EMPTY, ExecutionMode
from jobber._internal.common.datastructures import State
from jobber._internal.context import AppContext, JobContext, WorkerPools
from jobber._internal.exceptions import raise_app_already_started_error
from jobber._internal.injection import inject_context
from jobber._internal.middleware.base import build_middleware
from jobber._internal.middleware.exceptions import ExceptionMiddleware
from jobber._internal.routing import JobRoute, create_default_name
from jobber._internal.runner.runnable import iscoroutinerunnable
from jobber._internal.serializers.json import JSONSerializer
from jobber._internal.storage.dummy import DummyRepository
from jobber._internal.storage.sqlite import SQLiteJobRepository

if TYPE_CHECKING:
    import asyncio
    from collections.abc import AsyncIterator, Callable, Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType

    from jobber._internal.common.types import (
        ExceptionHandler,
        Lifespan,
        MappingExceptionHandlers,
    )
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.job import Job
    from jobber._internal.runner.runnable import Runnable
    from jobber._internal.serializers.abc import JobsSerializer
    from jobber._internal.storage.abc import JobRepository


_R = TypeVar("_R")
_P = ParamSpec("_P")
_AppType = TypeVar("_AppType", bound="Jobber")


@asynccontextmanager
async def _lifespan_stub(_: Jobber) -> AsyncIterator[None]:
    yield None


@final
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
        self._app_ctx = AppContext(
            _loop=loop,
            tz=tz or ZoneInfo("UTC"),
            durable=durable,
            worker_pools=WorkerPools(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            serializer=serializer or JSONSerializer(),
            asyncio_tasks=set(),
        )
        self._lifespan = self._run_lifespan(lifespan or _lifespan_stub)
        self._routes: dict[str, JobRoute[..., Any]] = {}
        self._job_registry: dict[str, Job[Any]] = {}
        self._middleware = deque(middleware or [])
        self._exc_handlers = dict(exception_handlers or {})
        self.state = State()

    def add_exception_handler(
        self,
        cls_exc: type[Exception],
        handler: ExceptionHandler,
    ) -> None:
        if self._app_ctx.app_started is True:
            raise_app_already_started_error("add_exception_handler")
        self._exc_handlers[cls_exc] = handler

    def add_middleware(self, middleware: BaseMiddleware) -> None:
        if self._app_ctx.app_started is True:
            raise_app_already_started_error("add_middleware")
        self._middleware.appendleft(middleware)

    async def _run_lifespan(
        self,
        user_lifespan: Lifespan[Any],
    ) -> AsyncIterator[None]:
        async with user_lifespan(self) as maybe_state:
            if maybe_state is not None:
                self.state.update(maybe_state)
            yield None

    async def _entry(self, context: JobContext) -> Any:  # noqa: ANN401
        runnable: Runnable[Any] = context.runnable
        inject_context(runnable, context)

        if iscoroutinerunnable(runnable):
            return await runnable()

        getloop = self._app_ctx.getloop
        match runnable.exec_mode:
            case ExecutionMode.THREAD:
                threadpool = self._app_ctx.worker_pools.threadpool
                return await getloop().run_in_executor(threadpool, runnable)
            case ExecutionMode.PROCESS:
                processpool = self._app_ctx.worker_pools.processpool
                return await getloop().run_in_executor(processpool, runnable)
            case _:
                return runnable()

    @overload
    def register(self, func: Callable[_P, _R]) -> JobRoute[_P, _R]: ...

    @overload
    def register(
        self,
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> Callable[[Callable[_P, _R]], JobRoute[_P, _R]]: ...

    @overload
    def register(
        self,
        func: Callable[_P, _R],
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> JobRoute[_P, _R]: ...

    def register(
        self,
        func: Callable[_P, _R] | None = None,
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> JobRoute[_P, _R] | Callable[[Callable[_P, _R]], JobRoute[_P, _R]]:
        if self._app_ctx.app_started is True:
            raise_app_already_started_error("register")

        wrapper = self._register(job_name=job_name, exec_mode=exec_mode)
        if callable(func):
            return wrapper(func)
        return wrapper  # pragma: no cover

    def _register(
        self,
        *,
        job_name: str | None,
        exec_mode: ExecutionMode,
    ) -> Callable[[Callable[_P, _R]], JobRoute[_P, _R]]:
        def wrapper(func: Callable[_P, _R]) -> JobRoute[_P, _R]:
            fname = job_name or create_default_name(func)
            if route := self._routes.get(fname):
                return cast("JobRoute[_P, _R]", route)

            route = JobRoute(
                state=self.state,
                job_name=fname,
                app_ctx=self._app_ctx,
                original_func=func,
                job_registry=self._job_registry,
                exec_mode=exec_mode,
            )
            _ = functools.update_wrapper(route, func)
            self._routes[fname] = route
            return route

        return wrapper

    def _build_middleware_chain(self) -> None:
        self._middleware.append(
            ExceptionMiddleware(
                self._exc_handlers,
                self._app_ctx.worker_pools.threadpool,
                self._app_ctx.getloop,
            )
        )
        middleware_chain = build_middleware(self._middleware, self._entry)
        for route in self._routes.values():
            route._middleware_chain = middleware_chain  # noqa: SLF001 # pyright: ignore[reportPrivateUsage]

    async def startup(self) -> None:
        await anext(self._lifespan)
        self._build_middleware_chain()
        self._app_ctx.app_started = True

    async def shutdown(self) -> None:
        self._app_ctx.close()
        await anext(self._lifespan, None)
        self._app_ctx.app_started = False

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
