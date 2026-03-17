import asyncio
import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeAlias

from benchmarks.latency_run import jobify_run_benchmarks
from .serializers import serializers_measure

Results: TypeAlias = dict[str, "float | dict[str, float]"]


@contextmanager
def timer() -> Iterator[None]:
    print("Running benchmarks...")
    start = time.perf_counter()
    yield None
    end = time.perf_counter() - start
    print("Benchmarks completed in: %.2fs.", end)


def write_results(results: Results) -> None:
    benches_file = Path("./benchmarks/benches.json")
    with benches_file.open(mode="w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    print("Results saved to: %s", benches_file)


async def main() -> None:
    results: Results = {}
    with timer():
        results |= serializers_measure()
        results |= await jobify_run_benchmarks()
    write_results(results)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )
    asyncio.run(main())
