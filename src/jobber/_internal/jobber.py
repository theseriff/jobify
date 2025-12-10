# ruff: noqa: SLF001
# pyright: reportPrivateUsage=false
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar
from zoneinfo import ZoneInfo

from jobber._internal.common.datastructures import State
from jobber._internal.configuration import JobberConfiguration, WorkerPools
from jobber._internal.injection import inject_context
from jobber._internal.middleware.base import build_middleware
from jobber._internal.middleware.exceptions import (
    ExceptionMiddleware,
    MappingExceptionHandlers,
)
from jobber._internal.middleware.retry import RetryMiddleware
from jobber._internal.middleware.timeout import TimeoutMiddleware
from jobber._internal.routers.root import JobRouter
from jobber._internal.serializers.json import JSONSerializer

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType

    from jobber._internal.common.types import Lifespan
    from jobber._internal.context import JobContext
    from jobber._internal.cron_parser import CronParser
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.runners import Runnable
    from jobber._internal.serializers.base import JobsSerializer
    from jobber._internal.storage.abc import JobRepository


ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")
AppT = TypeVar("AppT", bound="Jobber")


class Jobber(JobRouter):
    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo | None,
        durable: JobRepository,
        lifespan: Lifespan[AppT] | None,
        serializer: JobsSerializer | None,
        middleware: Sequence[BaseMiddleware] | None,
        exception_handlers: MappingExceptionHandlers | None,
        loop_factory: Callable[[], asyncio.AbstractEventLoop],
        threadpool_executor: ThreadPoolExecutor | None,
        processpool_executor: ProcessPoolExecutor | None,
        cron_parser_cls: type[CronParser],
    ) -> None:
        self.state: State = State()
        self.jobber_config: JobberConfiguration = JobberConfiguration(
            loop_factory=loop_factory,
            tz=tz or ZoneInfo("UTC"),
            durable=durable,
            worker_pools=WorkerPools(
                _processpool=processpool_executor,
                threadpool=threadpool_executor,
            ),
            serializer=serializer or JSONSerializer(),
            cron_parser_cls=cron_parser_cls,
            _tasks_registry=set(),
            _jobs_registry={},
        )
        super().__init__(
            state=self.state,
            lifespan=lifespan,
            middleware=middleware,
            jobber_config=self.jobber_config,
            exception_handlers=exception_handlers,
        )

    async def _entry(self, context: JobContext) -> Any:  # noqa: ANN401
        runnable: Runnable[Any] = context.runnable
        inject_context(runnable, context)
        return await runnable()

    def _build_middleware_chain(self) -> None:
        system_middlewares = (
            TimeoutMiddleware(),
            RetryMiddleware(),
            ExceptionMiddleware(self.task.exc_handlers, self.jobber_config),
        )
        user_middlewares = self.task.middleware
        user_middlewares.extend(system_middlewares)
        middleware_chain = build_middleware(user_middlewares, self._entry)
        for route in self.task._routes.values():
            route._middleware_chain = middleware_chain

    async def startup(self) -> None:
        self.jobber_config.app_started = True
        await self.task.emit_startup()
        self._build_middleware_chain()

        if crons := self.state.pop("__pending_cron_jobs__", []):
            pending = (route.schedule().cron(cron) for route, cron in crons)
            _ = await asyncio.gather(*pending)

    async def shutdown(self) -> None:
        self.jobber_config.app_started = False
        if tasks := self.jobber_config._tasks_registry:
            for task in tasks:
                _ = task.cancel()
            _ = await asyncio.gather(*tasks, return_exceptions=True)
            self.jobber_config._tasks_registry.clear()

        self.jobber_config.close()
        await self.task.emit_shutdown()

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
