import asyncio
import gc
import logging
import platform
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psutil

from benchmarks.jobify_app import jobify_run_benchmarks
from benchmarks.serializers import serializers_measure
from jobify import __version__


@contextmanager
def timer() -> Iterator[None]:
    print("Running benchmarks...")
    gc.disable()
    start = time.perf_counter()

    yield None

    end = time.perf_counter() - start
    gc.enable()
    print(f"Benchmarks completed in: {end:.2f}s.")


def write_results(results: str) -> None:
    print(results)
    benches_file = Path("./benchmarks/results.txt")
    with benches_file.open(mode="w", encoding="utf-8") as fp:
        _ = fp.write(results.strip())
    print(f"Results saved to: {benches_file}")


async def main() -> None:
    cpu_info = psutil.cpu_freq()
    results: list[str] = [
        f"jobify: {__version__}",
        f"OS: {platform.system()} {platform.release()}",
        f"Architecture: {platform.machine()}",
        f"CPU Physical cores: {psutil.cpu_count(logical=False)}",
        f"CPU Logical cores: {psutil.cpu_count(logical=True)}",
        f"CPU Max Frequency: {cpu_info.max:.2f}MHz"
        if cpu_info
        else "CPU Frequency: N/A",
        f"CPU Min Frequency: {cpu_info.min:.2f}MHz" if cpu_info else "",
        f"CPU Current Frequency: {cpu_info.current:.2f}MHz"
        if cpu_info
        else "",
    ]
    with timer():
        results.extend(
            enrich_results(serializers_measure(), name=" Serializers ")
        )
        results.extend(
            enrich_results(await jobify_run_benchmarks(), name=" Jobify APP ")
        )
    write_results("\n".join(results))


def enrich_results(results: list[str], name: str) -> list[str]:
    return [
        f"\n{name:=^60}",
        *results,
        f"{'=' * 60}",
    ]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )
    asyncio.run(main())
