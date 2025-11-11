from __future__ import annotations

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from iojobs._internal.durable.abc import JobRepository
    from iojobs._internal.serializers.abc import JobsSerializer


@dataclass(slots=True, kw_only=True)
class ExecutorsPool:
    _threadpool: ThreadPoolExecutor | None
    _processpool: ProcessPoolExecutor | None

    @property
    def threadpool(self) -> ThreadPoolExecutor:  # pragma: no cover
        if self._threadpool is None:
            self._threadpool = ThreadPoolExecutor()
        return self._threadpool

    @property
    def processpool(self) -> ProcessPoolExecutor:  # pragma: no cover
        if self._processpool is None:
            mp_ctx = multiprocessing.get_context("spawn")
            self._processpool = ProcessPoolExecutor(mp_context=mp_ctx)
        return self._processpool

    def close(self) -> None:
        if self._processpool is not None:
            self._processpool.shutdown(wait=True, cancel_futures=True)
        if self._threadpool is not None:
            self._threadpool.shutdown(wait=True, cancel_futures=True)


@dataclass(slots=True, kw_only=True)
class JobInnerScope:
    _loop: asyncio.AbstractEventLoop | None
    tz: ZoneInfo
    durable: JobRepository
    executors: ExecutorsPool
    serializer: JobsSerializer
    asyncio_tasks: set[asyncio.Task[Any]]  # pyright: ignore[reportExplicitAny]

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def close(self) -> None:
        self.executors.close()
