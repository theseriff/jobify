from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, overload

from jobber._internal.common.constants import (
    EMPTY,
    RunMode,
    get_run_mode,
)
from jobber._internal.common.datastructures import State
from jobber._internal.configuration import (
    JobberConfiguration,
    RouteConfiguration,
    WorkerPools,
)
from jobber._internal.exceptions import raise_app_already_started_error
from jobber._internal.injection import inject_context
from jobber._internal.middleware.base import build_middleware
from jobber._internal.middleware.exceptions import (
    ExceptionHandler,
    ExceptionHandlers,
    ExceptionMiddleware,
)
from jobber._internal.routing import JobRoute, create_default_name

if TYPE_CHECKING:
    from collections import deque
    from collections.abc import AsyncIterator, Callable, Mapping
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType
    from zoneinfo import ZoneInfo

    from jobber._internal.common.types import Lifespan
    from jobber._internal.context import JobContext
    from jobber._internal.cron_parser import CronParser
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.job import Job
    from jobber._internal.runner.runners import Runnable
    from jobber._internal.serializers.abc import JobsSerializer
    from jobber._internal.storage.abc import JobRepository


_R = TypeVar("_R")
_P = ParamSpec("_P")
_AppType = TypeVar("_AppType", bound="Jobber")


class Jobber:
    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo,
        durable: JobRepository,
        lifespan: Lifespan[_AppType],
        serializer: JobsSerializer,
        middleware: deque[BaseMiddleware],
        exception_handlers: ExceptionHandlers,
        loop_factory: Callable[[], asyncio.AbstractEventLoop],
        threadpool_executor: ThreadPoolExecutor | None,
        processpool_executor: ProcessPoolExecutor | None,
        cron_parser_cls: type[CronParser],
    ) -> None:
        self.jobber_config: JobberConfiguration = JobberConfiguration(
            loop_factory=loop_factory,
            asyncio_tasks=set(),
            tz=tz,
            durable=durable,
            worker_pools=WorkerPools(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            serializer=serializer,
            cron_parser_cls=cron_parser_cls,
        )
        self._lifespan: AsyncIterator[None] = self._run_lifespan(lifespan)
        self._routes: dict[str, JobRoute[..., Any]] = {}
        self._job_registry: dict[str, Job[Any]] = {}
        self._middleware: deque[BaseMiddleware] = middleware
        self._exc_handlers: ExceptionHandlers = exception_handlers
        self.state: State = State()

    def add_exception_handler(
        self,
        cls_exc: type[Exception],
        handler: ExceptionHandler,
    ) -> None:
        if self.jobber_config.app_started is True:
            raise_app_already_started_error("add_exception_handler")
        self._exc_handlers[cls_exc] = handler

    def add_middleware(self, middleware: BaseMiddleware) -> None:
        if self.jobber_config.app_started is True:
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
        return await runnable()

    @overload
    def register(self, func: Callable[_P, _R]) -> JobRoute[_P, _R]: ...

    @overload
    def register(
        self,
        *,
        retry: int = 1,
        timeout: float = 600,
        func_name: str | None = None,
        run_mode: RunMode = EMPTY,
        metadata: Mapping[str, Any] | None = None,
    ) -> Callable[[Callable[_P, _R]], JobRoute[_P, _R]]: ...

    @overload
    def register(
        self,
        func: Callable[_P, _R],
        *,
        retry: int = 1,
        timeout: float = 600,
        func_name: str | None = None,
        run_mode: RunMode = EMPTY,
        metadata: Mapping[str, Any] | None = None,
    ) -> JobRoute[_P, _R]: ...

    def register(  # noqa: PLR0913
        self,
        func: Callable[_P, _R] | None = None,
        *,
        retry: int = 1,
        timeout: float = 600,  # default 10 min.
        func_name: str | None = None,
        run_mode: RunMode = EMPTY,
        metadata: Mapping[str, Any] | None = None,
    ) -> JobRoute[_P, _R] | Callable[[Callable[_P, _R]], JobRoute[_P, _R]]:
        if self.jobber_config.app_started is True:
            raise_app_already_started_error("register")

        wrapper = self._register(
            retry=retry,
            timeout=timeout,
            func_name=func_name,
            run_mode=run_mode,
            metadata=metadata,
        )
        if callable(func):
            return wrapper(func)
        return wrapper  # pragma: no cover

    def _register(
        self,
        *,
        retry: int = 1,
        timeout: float = 600,  # default 10 min.
        func_name: str | None,
        run_mode: RunMode,
        metadata: Mapping[str, Any] | None,
    ) -> Callable[[Callable[_P, _R]], JobRoute[_P, _R]]:
        def wrapper(func: Callable[_P, _R]) -> JobRoute[_P, _R]:
            fname = func_name or create_default_name(func)
            if route := self._routes.get(fname):
                return cast("JobRoute[_P, _R]", route)

            is_async = asyncio.iscoroutinefunction(func)
            mode = get_run_mode(run_mode, is_async=is_async)
            route_config = RouteConfiguration(
                retry=retry,
                timeout=timeout,
                is_async=is_async,
                func_name=fname,
                run_mode=mode,
                metadata=metadata,
            )
            route = JobRoute(
                state=self.state,
                original_func=func,
                route_config=route_config,
                jobber_config=self.jobber_config,
                job_registry=self._job_registry,
            )
            _ = functools.update_wrapper(route, func)
            self._routes[fname] = route
            return route

        return wrapper

    def _build_middleware_chain(self) -> None:
        self._middleware.append(
            ExceptionMiddleware(
                self._exc_handlers,
                self.jobber_config.worker_pools.threadpool,
                self.jobber_config.loop_factory,
            )
        )
        middleware_chain = build_middleware(self._middleware, self._entry)
        for route in self._routes.values():
            route._middleware_chain = middleware_chain  # noqa: SLF001 # pyright: ignore[reportPrivateUsage]

    async def startup(self) -> None:
        await anext(self._lifespan)
        self._build_middleware_chain()
        self.jobber_config.app_started = True

    async def shutdown(self) -> None:
        self.jobber_config.app_started = False
        if tasks := self.jobber_config.asyncio_tasks:
            for task in tasks:
                _ = task.cancel()
            _ = await asyncio.gather(*tasks, return_exceptions=True)
            self.jobber_config.asyncio_tasks.clear()

        self.jobber_config.close()
        await anext(self._lifespan, None)

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
