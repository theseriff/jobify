import gc
import os
import statistics
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")
MIN_STDEV_SAMPLES = 2


@dataclass(frozen=True, slots=True)
class BenchmarkSettings:
    warmup: int
    rounds: int
    iterations: int

    @classmethod
    def from_env(
        cls,
        *,
        prefix: str,
        warmup: int,
        rounds: int,
        iterations: int,
    ) -> "BenchmarkSettings":
        return cls(
            warmup=_env_int(f"{prefix}_WARMUP", warmup),
            rounds=_env_int(f"{prefix}_ROUNDS", rounds),
            iterations=_env_int(f"{prefix}_ITERATIONS", iterations),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    operation: str
    iterations: int
    samples: tuple[float, ...]
    size_bytes: int | None = None

    @property
    def best_seconds(self) -> float:
        return min(self.samples)

    @property
    def median_seconds(self) -> float:
        return statistics.median(self.samples)

    @property
    def mean_seconds(self) -> float:
        return statistics.fmean(self.samples)

    @property
    def stdev_seconds(self) -> float:
        if len(self.samples) < MIN_STDEV_SAMPLES:
            return 0.0
        return statistics.stdev(self.samples)

    @property
    def best_ops_per_second(self) -> float:
        return self.iterations / self.best_seconds

    @property
    def best_microseconds_per_op(self) -> float:
        return (self.best_seconds / self.iterations) * 1_000_000


def measure_sync(
    name: str,
    operation: str,
    func: Callable[[], T],
    settings: BenchmarkSettings,
    *,
    size_bytes: int | None = None,
) -> BenchmarkResult:
    for _ in range(settings.warmup):
        _run_sync_iterations(func, settings.iterations)

    samples = tuple(
        _measure_sync_sample(func, settings.iterations) for _ in range(settings.rounds)
    )
    return BenchmarkResult(name, operation, settings.iterations, samples, size_bytes)


async def measure_async(
    name: str,
    operation: str,
    func: Callable[[], Awaitable[T]],
    settings: BenchmarkSettings,
) -> BenchmarkResult:
    for _ in range(settings.warmup):
        await _run_async_iterations(func, settings.iterations)

    samples = tuple(
        [
            await _measure_async_sample(func, settings.iterations)
            for _ in range(settings.rounds)
        ]
    )
    return BenchmarkResult(name, operation, settings.iterations, samples)


def format_results(results: list[BenchmarkResult]) -> list[str]:
    results.sort(key=lambda item: (item.operation, item.best_microseconds_per_op))
    lines = [
        f"{'Config Name':<38} | {'Op':<10} | {'Best µs/op':>10} | "
        f"{'Median µs/op':>12} | {'Ops/sec':>12} | {'Stdev %':>8} | {'Bytes':>8}",
        f"{'-' * 38} | {'-' * 10} | {'-' * 10} | {'-' * 12} | "
        f"{'-' * 12} | {'-' * 8} | {'-' * 8}",
    ]
    lines.extend(_format_result(result) for result in results)
    return lines


def format_skips(skips: list[str]) -> list[str]:
    if not skips:
        return []
    return ["", "Skipped:", *(f"- {skip}" for skip in skips)]


def _format_result(result: BenchmarkResult) -> str:
    size = "-" if result.size_bytes is None else str(result.size_bytes)
    stdev_pct = (
        0.0
        if result.mean_seconds == 0.0
        else (result.stdev_seconds / result.mean_seconds) * 100
    )
    median_us = (result.median_seconds / result.iterations) * 1_000_000
    return (
        f"{result.name:<38} | {result.operation:<10} | "
        f"{result.best_microseconds_per_op:>10.2f} | {median_us:>12.2f} | "
        f"{result.best_ops_per_second:>12.1f} | {stdev_pct:>7.2f}% | {size:>8}"
    )


def _measure_sync_sample(func: Callable[[], T], iterations: int) -> float:
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        _run_sync_iterations(func, iterations)
        return (time.perf_counter_ns() - start) / 1_000_000_000
    finally:
        if was_enabled:
            gc.enable()


async def _measure_async_sample(
    func: Callable[[], Awaitable[T]],
    iterations: int,
) -> float:
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        await _run_async_iterations(func, iterations)
        return (time.perf_counter_ns() - start) / 1_000_000_000
    finally:
        if was_enabled:
            gc.enable()


def _run_sync_iterations(func: Callable[[], T], iterations: int) -> None:
    for _ in range(iterations):
        func()


async def _run_async_iterations(
    func: Callable[[], Awaitable[T]],
    iterations: int,
) -> None:
    for _ in range(iterations):
        await func()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    parsed = int(value)
    if parsed <= 0:
        msg = f"{name} must be greater than 0"
        raise ValueError(msg)
    return parsed
