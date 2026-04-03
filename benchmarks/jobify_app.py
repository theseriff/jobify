import asyncio
import time
from typing import Literal, NamedTuple, cast

from adaptix import Retort

from jobify import Jobify
from jobify._internal.common.constants import EMPTY
from jobify.serializers import (
    ExtendedJSONSerializer,
    JSONSerializer,
    UnsafePickleSerializer,
)
from jobify.storage import SQLiteStorage, Storage


class CreateUser(NamedTuple):
    name: str
    email: str


class User(NamedTuple):
    id: str
    name: str
    email: str


async def task(dto: CreateUser) -> tuple[str, str, str]:
    return User("id", dto.name, dto.email)


class BenchResult(NamedTuple):
    name: str
    latency_ms: float
    throughput_tps: float


COOLDOWN_SLEEP = 3.0
AMOUNT_RUN = 10_000
WARMUP_RUNS = 100
ROUNDS = 3


async def jobify_run_benchmarks() -> list[str]:
    serializers = {
        "json": JSONSerializer(),
        "pickle": UnsafePickleSerializer(),
        "extended_json": ExtendedJSONSerializer(),
    }
    type_adapters = {
        "none": (None, None),
        "adaptix": (Retort(), Retort()),
    }
    bench_case = {
        "DummyDB+None+None": (False, EMPTY, (EMPTY, EMPTY)),
        **{
            f"Sqlite+{name_s}+{name_ta}": (SQLiteStorage(":memory:"), s, ta)
            for name_s, s in serializers.items()
            for name_ta, ta in type_adapters.items()
        },
    }
    final_results: list[BenchResult] = []

    for bench_name, (db, serializer, (dumper, loader)) in bench_case.items():
        app = Jobify(
            storage=cast("Storage | Literal[False]", db),
            serializer=serializer,
            dumper=dumper,
            loader=loader,
        )
        jobify_task = app.task(task)
        create_user_dto = CreateUser("Dilan", "ex@y.com")

        async with app:
            for _ in range(WARMUP_RUNS):
                _ = await task(create_user_dto)

            warmup_coros = (
                jobify_task.push(create_user_dto) for _ in range(WARMUP_RUNS)
            )
            jobs = await asyncio.gather(*warmup_coros)
            _ = await asyncio.gather(*(job.wait() for job in jobs))

            # --- 1. Latency ---
            latencies: list[float] = []
            for _ in range(ROUNDS):
                start = time.perf_counter()
                for _ in range(AMOUNT_RUN // 10):
                    job = await jobify_task.push(create_user_dto)
                    await job.wait()

                latencies.append(
                    (time.perf_counter() - start) / (AMOUNT_RUN // 10)
                )

            # --- 2. Throughput ---
            tps_results: list[float] = []
            for _ in range(ROUNDS):
                start = time.perf_counter()
                coros = (
                    jobify_task.push(create_user_dto)
                    for _ in range(AMOUNT_RUN)
                )
                _ = await asyncio.gather(*coros)
                await app.wait_all()
                elapsed = time.perf_counter() - start
                tps_results.append(AMOUNT_RUN / elapsed)

            avg_latency_ms = min(latencies) * 1000
            max_tps = max(tps_results)
            final_results.append(
                BenchResult(bench_name, avg_latency_ms, max_tps)
            )
            await asyncio.sleep(COOLDOWN_SLEEP)

    return prepare_report(final_results)


def prepare_report(results: list[BenchResult]) -> list[str]:
    results.sort(key=lambda x: x.throughput_tps, reverse=True)
    fmt_results: list[str] = [
        f"{'Config Name':<35} | {'Latency':<10} | {'Throughput':<12}",
        f"{'-' * 35} | {'-' * 10} | {'-' * 12}",
    ]
    fmt_results.extend(
        f"{r.name:<35} | {r.latency_ms:>7.3f} ms | {r.throughput_tps:>8.1f} TPS"  # noqa: E501
        for r in results
    )
    return fmt_results
