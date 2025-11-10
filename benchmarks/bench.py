import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeAlias

from .serializers import serializers_measure

Results: TypeAlias = dict[str, "float | dict[str, float]"]


@contextmanager
def timer() -> Iterator[None]:
    print("[INFO] Running benchmarks...")  # noqa: T201
    start = time.monotonic()
    yield None
    print(  # noqa: T201
        f"[INFO]Benchmarks completed in: {time.monotonic() - start:.2f}s.",
    )


if __name__ == "__main__":
    with timer():
        results: Results = {}
        results |= serializers_measure()
        benches_file = Path("./benchmarks/benches.json")
        with benches_file.open(mode="w", encoding="utf-8") as fp:
            json.dump(results, fp, indent=2)
