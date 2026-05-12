import asyncio
import gc
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import NamedTuple

from benchmarks.common import (
    BenchmarkResult,
    BenchmarkSettings,
    format_results,
    format_skips,
)
from benchmarks.registry import iter_available_serializers, iter_available_type_adapters
from jobify import Jobify
from jobify._internal.storage.base import Storage
from jobify._internal.typeadapter.base import Dumper, Loader
from jobify.serializers import Serializer
from jobify.storage import SQLiteStorage


class CreateUser(NamedTuple):
    name: str
    email: str


class User(NamedTuple):
    id: str
    name: str
    email: str


@dataclass(frozen=True, slots=True)
class JobifyBenchCase:
    name: str
    storage_factory: Callable[[], Storage | bool]
    serializer: Serializer | None
    dumper: Dumper | None
    loader: Loader | None


async def task(dto: CreateUser) -> User:
    return User("id", dto.name, dto.email)


async def jobify_run_benchmarks() -> list[str]:
    latency_settings = BenchmarkSettings.from_env(
        prefix="JOBIFY_BENCH_APP_LATENCY",
        warmup=1,
        rounds=5,
        iterations=200,
    )
    throughput_settings = BenchmarkSettings.from_env(
        prefix="JOBIFY_BENCH_APP_THROUGHPUT",
        warmup=1,
        rounds=5,
        iterations=1_000,
    )
    bench_cases, skips = _build_cases()
    results: list[BenchmarkResult] = []

    for case in bench_cases:
        print(f"bench case: {case.name}")
        results.append(await _measure_latency(case, latency_settings))
        results.append(await _measure_throughput(case, throughput_settings))
        await asyncio.sleep(0)

    return [*format_results(results), *format_skips(skips)]


def _build_cases() -> tuple[list[JobifyBenchCase], list[str]]:
    serializers, serializer_skips = iter_available_serializers("json")
    adapters, adapter_skips = iter_available_type_adapters()
    cases = [
        JobifyBenchCase(
            "dummy_storage+default_serializer+none",
            lambda: False,
            None,
            None,
            None,
        )
    ]

    cases.extend(
        JobifyBenchCase(
            f"sqlite+{serializer_name}+{adapter_name}",
            lambda: SQLiteStorage(":memory:"),
            serializer,
            dumper,
            loader,
        )
        for serializer_name, serializer in serializers
        for adapter_name, (dumper, loader) in adapters
    )
    return cases, [*serializer_skips, *adapter_skips]


async def _measure_latency(
    case: JobifyBenchCase,
    settings: BenchmarkSettings,
) -> BenchmarkResult:
    samples: list[float] = []
    for _ in range(settings.rounds):
        sample = await _measure_jobify_sample(
            case,
            lambda jobify_task, dto: _run_latency(
                jobify_task,
                dto,
                settings.iterations,
            ),
            warmup_iterations=settings.warmup,
        )
        samples.append(sample)
    return BenchmarkResult(case.name, "latency", settings.iterations, tuple(samples))


async def _measure_throughput(
    case: JobifyBenchCase,
    settings: BenchmarkSettings,
) -> BenchmarkResult:
    samples: list[float] = []
    for _ in range(settings.rounds):
        sample = await _measure_jobify_sample(
            case,
            lambda jobify_task, dto: _run_throughput(
                jobify_task,
                dto,
                settings.iterations,
            ),
            warmup_iterations=settings.warmup,
        )
        samples.append(sample)
    return BenchmarkResult(case.name, "throughput", settings.iterations, tuple(samples))


async def _measure_jobify_sample(
    case: JobifyBenchCase,
    measured: Callable[[object, CreateUser], Awaitable[float]],
    *,
    warmup_iterations: int,
) -> float:
    app = Jobify(
        storage=case.storage_factory(),
        serializer=case.serializer,
        dumper=case.dumper,
        loader=case.loader,
    )
    jobify_task = app.task(task)
    dto = CreateUser("Dilan", "ex@y.com")

    async with app:
        await _run_latency(jobify_task, dto, warmup_iterations)
        gc.collect()
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            start = time.perf_counter_ns()
            await measured(jobify_task, dto)
            return (time.perf_counter_ns() - start) / 1_000_000_000
        finally:
            if was_enabled:
                gc.enable()


async def _run_latency(jobify_task: object, dto: CreateUser, iterations: int) -> float:
    for _ in range(iterations):
        job = await jobify_task.push(dto)
        await job.wait()
    return 0.0


async def _run_throughput(
    jobify_task: object,
    dto: CreateUser,
    iterations: int,
) -> float:
    jobs = await asyncio.gather(*(jobify_task.push(dto) for _ in range(iterations)))
    await asyncio.gather(*(job.wait() for job in jobs))
    return 0.0
