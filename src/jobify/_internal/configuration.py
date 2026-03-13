from __future__ import annotations

import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict, final

from jobify._internal.common.constants import INFINITY
from jobify._internal.scheduler.misfire_policy import (
    GracePolicy,
    MisfirePolicy,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from jobify._internal.common.constants import RunMode
    from jobify._internal.common.types import (
        LoopFactory,
        MappingExceptionHandlers,
    )
    from jobify._internal.cron_parser import CronFactory
    from jobify._internal.serializers.base import Serializer
    from jobify._internal.storage.base import Storage
    from jobify._internal.typeadapter.base import Dumper, Loader


@final
class WorkerPools:
    __slots__: tuple[str, ...] = ("_processpool", "threadpool")

    def __init__(
        self,
        *,
        _processpool: ProcessPoolExecutor | None = None,
        threadpool: ThreadPoolExecutor | None = None,
    ) -> None:
        self._processpool = _processpool
        self.threadpool = threadpool

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


@final
class JobifyConfiguration:
    __slots__: tuple[str, ...] = (
        "app_started",
        "cron_factory",
        "dumper",
        "getloop",
        "loader",
        "serializer",
        "storage",
        "tz",
        "worker_pools",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo,
        dumper: Dumper,
        loader: Loader,
        storage: Storage,
        getloop: LoopFactory,
        serializer: Serializer,
        worker_pools: WorkerPools,
        cron_factory: CronFactory,
        app_started: bool = False,
    ) -> None:
        self.tz = tz
        self.dumper = dumper
        self.loader = loader
        self.storage = storage
        self.getloop = getloop
        self.serializer = serializer
        self.worker_pools = worker_pools
        self.cron_factory = cron_factory
        self.app_started = app_started


@dataclass(slots=True, kw_only=True, order=True)
class Cron:
    expression: str = field(kw_only=False)
    max_runs: int = INFINITY
    max_failures: int = 10
    misfire_policy: MisfirePolicy | GracePolicy = MisfirePolicy.ONCE
    start_date: datetime | None = None
    args: Collection[Any] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]

    def __post_init__(self) -> None:
        if self.max_failures < 1:
            msg = (
                "max_cron_failures must be >= 1."
                " Use 1 for 'stop on first error'."
            )
            raise ValueError(msg)


class RouteOptions(TypedDict, total=False):
    name: str
    cron: Cron | str
    retry: int
    timeout: float
    durable: bool
    run_mode: RunMode
    metadata: Mapping[str, Any]
    exception_handlers: MappingExceptionHandlers
