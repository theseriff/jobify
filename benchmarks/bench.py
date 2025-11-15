import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeAlias

from .serializers import serializers_measure

logger = logging.getLogger(__name__)

Results: TypeAlias = dict[str, "float | dict[str, float]"]


@contextmanager
def timer() -> Iterator[None]:
    logger.info("Running benchmarks...")
    start = time.monotonic()
    yield None
    logger.info("Benchmarks completed in: %.2fs.", time.monotonic() - start)


def write_results(results: Results) -> None:
    benches_file = Path("./benchmarks/benches.json")
    with benches_file.open(mode="w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)
    logger.info("Results saved to: %s", benches_file)


def main() -> None:
    results: Results = {}
    with timer():
        results |= serializers_measure()
    write_results(results)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )
    main()
