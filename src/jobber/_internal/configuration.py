from __future__ import annotations

import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Mapping
    from zoneinfo import ZoneInfo

    from jobber._internal.common.constants import RunMode
    from jobber._internal.common.types import LoopFactory
    from jobber._internal.cron_parser import CronParser
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
class JobberConfiguration:
    loop_factory: LoopFactory
    tz: ZoneInfo
    durable: JobRepository
    worker_pools: WorkerPools
    serializer: JobsSerializer
    cron_parser_cls: type[CronParser]
    app_started: bool = False
    asyncio_tasks: set[asyncio.Task[Any]]

    def close(self) -> None:
        self.worker_pools.close()


@dataclass(slots=True, kw_only=True, frozen=True)
class RouteConfiguration:
    retry: int
    timeout: float
    is_async: bool
    func_name: str
    run_mode: RunMode
    metadata: Mapping[str, Any] | None
