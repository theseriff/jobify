import asyncio
import gc
import time
from typing import Literal, NamedTuple

from adaptix import Retort

from jobify import Jobify
from jobify.serializers import JSONSerializer, UnsafePickleSerializer
from jobify.storage import SQLiteStorage, Storage


class CreateUser(NamedTuple):
    name: str
    email: str


class User(NamedTuple):
    id: str
    name: str
    email: str


def task(_: CreateUser) -> tuple[str, str, str]:
    return User("some_id", "Bob", "example@yahoo.com")


class BenchResult(NamedTuple):
    name: str
    latency_ms: float
    throughput_tps: float


AMOUNT_RUN = 10_000
WARMUP_RUNS = 100
ROUNDS = 3


async def jobify_run_benchmarks() -> dict[str, dict[str, float]]:
    databases: dict[str, Storage | Literal[False]] = {
        "dummyDB": False,
        "sqlite": SQLiteStorage(database=":memory:"),
    }
    serializers = {
        "pickle": UnsafePickleSerializer(),
        "json": JSONSerializer(),
    }
    type_adapters = {
        "none": (None, None),
        "adaptix": (Retort(), Retort()),
    }

    final_results: list[BenchResult] = []

    for db_name, db in databases.items():
        for set_name, serializer in serializers.items():
            for ta_name, (dumper, loader) in type_adapters.items():
                config_name = f"{db_name}+{set_name}+{ta_name}"

                app = Jobify(
                    storage=db,
                    serializer=serializer,
                    dumper=dumper,
                    loader=loader,
                )
                jobify_task = app.task(task)

                async with app:
                    # --- 1. Latency ---
                    latencies: list[float] = []
                    for _ in range(ROUNDS):
                        gc.disable()
                        start = time.perf_counter()
                        for _ in range(AMOUNT_RUN // 10):
                            job = await jobify_task.push(
                                CreateUser("Dilan", "ex@y.com")
                            )
                            await job.wait()
                        latencies.append(
                            (time.perf_counter() - start) / (AMOUNT_RUN // 10)
                        )
                        gc.enable()

                    avg_latency_ms = min(latencies) * 1000

                    # --- 2. Throughput ---
                    async def push_and_wait() -> None:
                        job = await jobify_task.push(  # noqa: B023
                            CreateUser("Dilan", "ex@y.com")
                        )
                        await job.wait()

                    tps_results: list[float] = []
                    for _ in range(ROUNDS):
                        coros = [push_and_wait() for _ in range(AMOUNT_RUN)]
                        gc.disable()
                        start = time.perf_counter()
                        _ = await asyncio.gather(*coros)
                        elapsed = time.perf_counter() - start
                        gc.enable()
                        tps_results.append(AMOUNT_RUN / elapsed)

                    max_tps = max(tps_results)

                    final_results.append(
                        BenchResult(config_name, avg_latency_ms, max_tps)
                    )

    return prepare_report(final_results)


def prepare_report(results: list[BenchResult]) -> dict[str, dict[str, float]]:
    fmt_results: dict[str, dict[str, float]] = {}

    print(f"\n{' Configuration ':=^60}")
    print(f"{'Config Name':<35} | {'Latency':<10} | {'Throughput':<12}")
    print(f"{'-' * 35} | {'-' * 10} | {'-' * 12}")
    for r in sorted(results, key=lambda x: x.throughput_tps, reverse=True):
        fmt_results[r.name] = {
            "latency_ms": round(r.latency_ms, 6),
            "throughput_tps": round(r.throughput_tps, 6),
        }
        print(
            f"{r.name:<35} | {r.latency_ms:>7.3f} ms | {r.throughput_tps:>8.1f} TPS"  # noqa: E501
        )
    print(f"{'=' * 60}\n")

    return fmt_results
