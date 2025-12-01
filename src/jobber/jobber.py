"""Jobber entrypoint."""

from __future__ import annotations

from collections import deque
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Literal, TypeVar
from zoneinfo import ZoneInfo

from jobber._internal.jobber import Jobber as _Jobber
from jobber._internal.storage.dummy import DummyRepository
from jobber._internal.storage.sqlite import SQLiteJobRepository
from jobber.crontab import Crontab
from jobber.serializers import JSONSerializer

if TYPE_CHECKING:
    import asyncio
    from collections.abc import AsyncIterator, Sequence
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    from jobber._internal.common.types import (
        Lifespan,
        MappingExceptionHandlers,
    )
    from jobber._internal.cron_parser import CronParser
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.serializers.abc import JobsSerializer
    from jobber._internal.storage.abc import JobRepository


_AppType = TypeVar("_AppType", bound="Jobber")


@asynccontextmanager
async def _lifespan_stub(_: Jobber) -> AsyncIterator[None]:
    yield None


class Jobber(_Jobber):
    """Jobber is the main app for scheduling and managing background jobs.

    It provides a flexible and extensible framework for defining, running,
    and persisting jobs, supporting various executors, middleware, and
    serialization options.
    """

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
        cron_parser_cls: type[CronParser] | None = None,
    ) -> None:
        """Initialize a `Jobber` instance."""
        if durable is False:
            durable = DummyRepository()
        elif durable is None:
            durable = SQLiteJobRepository()
        super().__init__(
            tz=tz or ZoneInfo("UTC"),
            loop=loop,
            durable=durable,
            lifespan=lifespan or _lifespan_stub,
            serializer=serializer or JSONSerializer(),
            middleware=deque(middleware or []),
            exception_handlers=dict(exception_handlers or {}),
            threadpool_executor=threadpool_executor,
            processpool_executor=processpool_executor,
            cron_parser_cls=cron_parser_cls or Crontab,
        )
