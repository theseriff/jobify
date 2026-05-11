import multiprocessing
import random
import sys
import uuid
from collections.abc import Collection, Mapping
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NamedTuple, Protocol, TypedDict
from zoneinfo import ZoneInfo

from jobify._internal.common.constants import INFINITY, RunMode
from jobify._internal.common.types import (
    LoopFactory,
    MappingExceptionHandlers,
)
from jobify._internal.cron_parser import CronFactory
from jobify._internal.scheduler.misfire_policy import (
    GracePolicy,
    MisfirePolicy,
)
from jobify._internal.serializers.base import Serializer
from jobify._internal.storage.base import Storage
from jobify._internal.typeadapter.base import Dumper, Loader


class UUIDGenerator(Protocol):
    def __call__(self) -> uuid.UUID: ...


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
        "uuid_generator",
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
        uuid_generator: UUIDGenerator,
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
        self.uuid_generator = uuid_generator
        self.app_started = app_started


@dataclass(slots=True, kw_only=True, order=True)
class Cron:
    """Configuration for cron-based job scheduling.

    Attributes:
        expression: The crontab-formatted expression.
        max_runs: Maximum number of times the job can be triggered.
            Defaults to infinity.
        max_failures: Maximum number of consecutive failures before disabling the job.
            Defaults to 10.
        misfire_policy: Policy to handle missed job executions.
            Defaults to MisfirePolicy.ONCE.
        start_date: Optional datetime when the cron job becomes active.
        args: Positional arguments to pass to the job.
        kwargs: Keyword arguments to pass to the job.

    """

    expression: str = field(kw_only=False)
    max_runs: int = INFINITY
    max_failures: int = 10
    misfire_policy: MisfirePolicy | GracePolicy = MisfirePolicy.ONCE
    start_date: datetime | None = None
    args: Collection[Any] = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]

    def __post_init__(self) -> None:
        if self.max_failures < 1:
            msg = "max_cron_failures must be >= 1. Use 1 for 'stop on first error'."
            raise ValueError(msg)


class RouteOptions(TypedDict, total=False):
    name: str
    cron: Cron | str
    retry: "int | SmartRetry"
    timeout: float
    durable: bool
    run_mode: RunMode
    metadata: Mapping[str, Any]
    exception_handlers: MappingExceptionHandlers


class SmartRetry(NamedTuple):
    """Immutable configuration and delay logic for retrying failed operations.

    Uses exponential backoff with optional equal jitter to spread retry load.
    Designed as a value object: cheap to copy, safe to share across threads.

    Attributes:
        retries: Number of retries that should be performed after the first failure.
            Must be >= 0. A value of 0 means no retries.
        initial_delay: Base delay in seconds before the first retry.
        max_delay: Upper bound on computed delay, regardless of backoff growth.
        backoff_factor: Multiplier applied per retry. ``1.0`` gives constant
            delay, ``2.0`` gives classic exponential backoff.
        jitter: If ``True``, randomises delay in ``[delay/2, delay]`` to avoid
            thundering-herd. If ``False``, delay is deterministic.
        include_exceptions: Exception types that trigger a retry.
            Defaults to ``(Exception,) — retries on anything.
        exclude_exceptions: Exception types that are re-raised immediately,
            even if they match ``include_exceptions``. Takes priority.

    """

    retries: int
    initial_delay: float = 0.5
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    include_exceptions: tuple[type[Exception], ...] = (Exception,)
    exclude_exceptions: tuple[type[Exception], ...] = ()

    def compute_delay(self, attempt: int) -> float:
        delay = min(
            self.initial_delay * self.backoff_factor ** (attempt - 1),
            self.max_delay,
        )
        if self.jitter:
            delay /= 2
            return delay + random.uniform(0, delay)  # nosec # noqa: S311
        return delay
