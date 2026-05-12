"""CodSpeed benchmarks for jobify.

Covers the two main hot paths: serializer round-trips and task
push-wait cycles.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

from jobify import Jobify
from jobify.serializers import (
    ExtendedJSONSerializer,
    JSONSerializer,
    UnsafePickleSerializer,
)
from jobify.storage import SQLiteStorage

if TYPE_CHECKING:
    import pytest

    from jobify._internal.serializers.json_extended import SupportedTypes


# ---------------------------------------------------------------------------
# Serializer data fixtures
# ---------------------------------------------------------------------------


@dataclass
class BenchDataclass:
    id: int
    name: str
    tags: list[str]
    meta: dict[str, int]


@dataclass
class NestedBenchDataclass:
    bench: BenchDataclass


class BenchNamedTuple(NamedTuple):
    x: float
    y: float
    label: str


SERIALIZABLE_DATA: dict[str, SupportedTypes] = {
    "none_value": None,
    "boolean_true": True,
    "positive_int": 42,
    "positive_float": 3.14159,
    "simple_string": "Hello, World!",
    "binary_data": b"binary_data_bytes",
    "simple_set": {1, 2, 3, 4, 5},
    "simple_list": [1, 2, 3, 4, 5],
    "nested_list": [[1, 2], [3, 4], [5, 6]],
    "simple_tuple": (1, "two", 3.0, None),
    "simple_dict": {"name": "Alice", "age": 30, "is_active": True},
    "nested_dict": {
        "user": {
            "id": 12345,
            "profile": {
                "first_name": "John",
                "last_name": "Doe",
                "preferences": {"theme": "dark", "language": "en"},
            },
        },
    },
    "complex_structure": {
        "users": [
            {
                "id": 1,
                "name": "Alice",
                "tags": {"admin", "moderator"},
                "scores": (95, 87, 92),
            },
            {
                "id": 2,
                "name": "Bob",
                "tags": {"user"},
                "scores": (78, 85, 80),
            },
        ],
    },
    "custom_types": {
        "dataclasses_simple": BenchDataclass(1, "test", ["a"], {"x": 1}),
        "namedtuples_simple": BenchNamedTuple(1.1, 2.2, "point"),
        "dataclasses_list": [BenchDataclass(i, f"nm_{i}", [], {}) for i in range(20)],
    },
}


# ---------------------------------------------------------------------------
# Serializer benchmarks
# ---------------------------------------------------------------------------


def test_pickle_roundtrip(benchmark: pytest.BenchmarkFixture) -> None:
    serializer = UnsafePickleSerializer()

    def roundtrip() -> dict[str, SupportedTypes]:
        encoded = serializer.dumpb(SERIALIZABLE_DATA)
        return serializer.loadb(encoded)

    result = benchmark(roundtrip)
    assert result == SERIALIZABLE_DATA


def test_extended_json_roundtrip(
    benchmark: pytest.BenchmarkFixture,
) -> None:
    serializer = ExtendedJSONSerializer(
        (BenchDataclass, NestedBenchDataclass, BenchNamedTuple)
    )

    def roundtrip() -> dict[str, SupportedTypes]:
        encoded = serializer.dumpb(SERIALIZABLE_DATA)
        return serializer.loadb(encoded)

    result = benchmark(roundtrip)
    assert result == SERIALIZABLE_DATA


def test_json_serializer_roundtrip(
    benchmark: pytest.BenchmarkFixture,
) -> None:
    serializer = JSONSerializer()
    simple_data: dict[str, SupportedTypes] = {
        "name": "Alice",
        "age": 30,
        "is_active": True,
        "scores": [95, 87, 92],
    }

    def roundtrip() -> dict[str, SupportedTypes]:
        encoded = serializer.dumpb(simple_data)
        return serializer.loadb(encoded)

    result = benchmark(roundtrip)
    assert result == simple_data


# ---------------------------------------------------------------------------
# Task push/wait benchmarks
# ---------------------------------------------------------------------------


class CreateUser(NamedTuple):
    name: str
    email: str


async def dummy_task(dto: CreateUser) -> tuple[str, str, str]:
    return ("id", dto.name, dto.email)


def test_task_push_wait_no_storage(
    benchmark: pytest.BenchmarkFixture,
) -> None:
    """Benchmark task push and wait without persistence."""

    def run() -> None:
        async def _inner() -> None:
            app = Jobify()
            jobify_task = app.task(dummy_task)
            dto = CreateUser("Dilan", "ex@y.com")

            async with app:
                job = await jobify_task.push(dto)
                await job.wait()

        asyncio.run(_inner())

    benchmark(run)


def test_task_push_wait_sqlite_json(
    benchmark: pytest.BenchmarkFixture,
) -> None:
    """Benchmark task push and wait with SQLite storage and JSON serializer."""

    def run() -> None:
        async def _inner() -> None:
            app = Jobify(
                storage=SQLiteStorage(":memory:"),
                serializer=JSONSerializer(),
            )
            jobify_task = app.task(dummy_task)
            dto = CreateUser("Dilan", "ex@y.com")

            async with app:
                job = await jobify_task.push(dto)
                await job.wait()

        asyncio.run(_inner())

    benchmark(run)


def test_task_push_wait_sqlite_pickle(
    benchmark: pytest.BenchmarkFixture,
) -> None:
    """Benchmark task push and wait with SQLite + pickle serializer."""

    def run() -> None:
        async def _inner() -> None:
            app = Jobify(
                storage=SQLiteStorage(":memory:"),
                serializer=UnsafePickleSerializer(),
            )
            jobify_task = app.task(dummy_task)
            dto = CreateUser("Dilan", "ex@y.com")

            async with app:
                job = await jobify_task.push(dto)
                await job.wait()

        asyncio.run(_inner())

    benchmark(run)


def test_task_throughput_no_storage(
    benchmark: pytest.BenchmarkFixture,
) -> None:
    """Benchmark pushing many tasks concurrently without persistence."""

    def run() -> None:
        async def _inner() -> None:
            app = Jobify()
            jobify_task = app.task(dummy_task)
            dto = CreateUser("Dilan", "ex@y.com")

            async with app:
                coros = (jobify_task.push(dto) for _ in range(100))
                await asyncio.gather(*coros)
                await app.wait_all()

        asyncio.run(_inner())

    benchmark(run)
