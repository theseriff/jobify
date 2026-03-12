import time
from typing import Literal, NamedTuple

from jobify import Jobify
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


def task(_: CreateUser) -> tuple[str, str, str]:
    return User("some_id", "Bob", "example@yahoo.com")


AMOUNT_RUN = 10_000


def directly_run() -> float:
    start = time.perf_counter()
    for _ in range(AMOUNT_RUN):
        _ = task(CreateUser("Dilan", "example@yahoo.com"))
    return time.perf_counter() - start


async def jobify_matrix_measure() -> dict[str, float]:
    databases: dict[str, Storage | Literal[False]] = {
        "nondb": False,
        "sqlite": SQLiteStorage(database="benchmarks/bench.sqlite"),
    }
    serializers = {
        "pickle": UnsafePickleSerializer(),
        "json": JSONSerializer(),
        "extended_json": ExtendedJSONSerializer(),
    }
    results: dict[str, float] = {}

    for db_name, db in databases.items():
        for serializer_name, serializer in serializers.items():
            app = Jobify(storage=db, serializer=serializer)

            jobify_task = app.task(task)

            async with app:
                start = time.perf_counter()
                for _ in range(AMOUNT_RUN):
                    job = await jobify_task.push(
                        CreateUser("Dilan", "example@yahoo.com"),
                    )
                    await job.wait()

                result = round(time.perf_counter() - start, 5)
                results[f"push_{db_name}_{serializer_name}"] = result

            if isinstance(app.configs.storage, SQLiteStorage):
                app.configs.storage.database.unlink()

    return results


async def latency_measure() -> dict[str, dict[str, float]]:
    return {
        "latency": {
            "directly_run": round(directly_run(), 5),
            **(await jobify_matrix_measure()),
        }
    }
