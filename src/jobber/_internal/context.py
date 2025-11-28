import asyncio
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.runner.job import Job
from jobber._internal.runner.runnable import Runnable
from jobber._internal.serializers.abc import JobsSerializer
from jobber._internal.storage.abc import JobRepository


@dataclass(slots=True, kw_only=True)
class WorkerPools:
    _processpool: ProcessPoolExecutor | None
    threadpool: ThreadPoolExecutor | None = None

    @property
    def processpool(self) -> ProcessPoolExecutor:  # pragma: no cover
        if self._processpool is None:
            if sys.platform in ("win32", "darwin"):
                start_method = "spawn"
            elif "forkserver" in multiprocessing.get_all_start_methods():
                start_method = "forkserver"
            else:
                start_method = "spawn"
            mp_ctx = multiprocessing.get_context(start_method)
            self._processpool = ProcessPoolExecutor(mp_context=mp_ctx)
        return self._processpool

    def close(self) -> None:
        if self._processpool is not None:
            self._processpool.shutdown(wait=True, cancel_futures=True)
            self._processpool = None


@dataclass(slots=True, kw_only=True)
class AppContext:
    _loop: asyncio.AbstractEventLoop | None
    tz: ZoneInfo
    durable: JobRepository
    worker_pools: WorkerPools
    serializer: JobsSerializer
    asyncio_tasks: set[asyncio.Task[Any]]
    app_started: bool = False

    def getloop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def close(self) -> None:
        self.worker_pools.close()


@dataclass(slots=True, kw_only=True)
class JobContext:
    job: Job[Any]
    state: State
    request_state: RequestState
    runnable: Runnable[Any]
