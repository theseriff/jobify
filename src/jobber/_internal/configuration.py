from __future__ import annotations

import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

from typing_extensions import NotRequired

from jobber._internal.common.constants import INFINITY

if TYPE_CHECKING:
    from collections.abc import Mapping
    from zoneinfo import ZoneInfo

    from jobber._internal.common.constants import RunMode
    from jobber._internal.common.types import LoopFactory
    from jobber._internal.cron_parser import CronFactory
    from jobber._internal.serializers.base import Serializer
    from jobber._internal.storage.abc import Storage
    from jobber._internal.typeadapter.base import Dumper, Loader


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
    tz: ZoneInfo
    dumper: Dumper
    loader: Loader
    storage: Storage
    getloop: LoopFactory
    serializer: Serializer
    worker_pools: WorkerPools
    cron_factory: CronFactory
    app_started: bool = False


@dataclass(slots=True, kw_only=True, frozen=True)
class Cron:
    expression: str = field(kw_only=False)
    max_runs: int = INFINITY
    max_failures: int = 10

    def __post_init__(self) -> None:
        if self.max_failures < 1:
            msg = (
                "max_cron_failures must be >= 1."
                " Use 1 for 'stop on first error'."
            )
            raise ValueError(msg)


class RouteOptions(TypedDict):
    func_name: NotRequired[str]
    cron: NotRequired[Cron | str]
    retry: NotRequired[int]
    timeout: NotRequired[float]
    durable: NotRequired[bool]
    run_mode: NotRequired[RunMode]
    metadata: NotRequired[Mapping[str, Any]]
