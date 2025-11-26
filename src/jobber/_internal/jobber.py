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
    overload,
)
from zoneinfo import ZoneInfo

from jobber._internal.common.constants import EMPTY, ExecutionMode
from jobber._internal.common.datastructures import State
from jobber._internal.context import AppContext, WorkerPools
from jobber._internal.middleware.exceptions import ExceptionMiddleware
from jobber._internal.routing import Route, create_default_name
from jobber._internal.serializers.json import JSONSerializer
from jobber._internal.storage.dummy import DummyRepository
from jobber._internal.storage.sqlite import SQLiteJobRepository

if TYPE_CHECKING:
    import asyncio
    from collections.abc import AsyncIterator, Callable, Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType

    from jobber._internal.common.types import (
        Lifespan,
        MappingExceptionHandlers,
    )
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.job import Job
    from jobber._internal.serializers.abc import JobsSerializer
    from jobber._internal.storage.abc import JobRepository


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
            worker_pools=WorkerPools(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            serializer=serializer or JSONSerializer(),
            asyncio_tasks=set(),
        )
        self._lifespan: AsyncIterator[None] = self._run_lifespan(
            lifespan or _lifespan_stub,
        )
        self._routes: dict[str, Route[..., Any]] = {}
        self._job_registry: dict[str, Job[Any]] = {}
        user_exception_handlers = exception_handlers or {}
        self.exception_handler: ExceptionMiddleware = ExceptionMiddleware(
            {**user_exception_handlers},
            threadpool_executor,
            self._app_ctx.getloop,
        )
        self._user_middlewares: deque[BaseMiddleware] = deque(
            [*(middleware or []), self.exception_handler],
        )
        self.state: State = State()

    @overload
    def register(
        self,
        func: Callable[_FuncParams, _ReturnType],
    ) -> Route[_FuncParams, _ReturnType]: ...

    @overload
    def register(
        self,
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> Callable[
        [Callable[_FuncParams, _ReturnType]],
        Route[_FuncParams, _ReturnType],
    ]: ...

    @overload
    def register(
        self,
        func: Callable[_FuncParams, _ReturnType],
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> Route[_FuncParams, _ReturnType]: ...

    def register(
        self,
        func: Callable[_FuncParams, _ReturnType] | None = None,
        *,
        job_name: str | None = None,
        exec_mode: ExecutionMode = EMPTY,
    ) -> (
        Route[_FuncParams, _ReturnType]
        | Callable[
            [Callable[_FuncParams, _ReturnType]],
            Route[_FuncParams, _ReturnType],
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
        Route[_FuncParams, _ReturnType],
    ]:
        def wrapper(
            func: Callable[_FuncParams, _ReturnType],
        ) -> Route[_FuncParams, _ReturnType]:
            fname = job_name or create_default_name(func)
            if route := self._routes.get(fname):
                return cast("Route[_FuncParams, _ReturnType]", route)

            route = Route(
                state=self.state,
                job_name=fname,
                app_ctx=self._app_ctx,
                original_func=func,
                job_registry=self._job_registry,
                exec_mode=exec_mode,
                user_middleware=self._user_middlewares,
            )
            _ = functools.update_wrapper(route, func)
            self._routes[fname] = route
            return route

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
