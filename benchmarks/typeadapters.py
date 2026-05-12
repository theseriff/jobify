from typing import NamedTuple

from benchmarks.common import (
    BenchmarkResult,
    BenchmarkSettings,
    format_results,
    format_skips,
    measure_sync,
)
from benchmarks.registry import iter_available_type_adapters
from jobify._internal.typeadapter.base import Dumper, Loader


class CreateUser(NamedTuple):
    name: str
    email: str
    roles: tuple[str, ...]


DTO = CreateUser("Dilan", "ex@y.com", ("admin", "user"))
RAW_DTO = {"name": "Dilan", "email": "ex@y.com", "roles": ["admin", "user"]}


def type_adapters_measure() -> list[str]:
    settings = BenchmarkSettings.from_env(
        prefix="JOBIFY_BENCH_TYPEADAPTER",
        warmup=2,
        rounds=5,
        iterations=2_000,
    )
    adapters, skips = iter_available_type_adapters(include_jobify_disabled=True)
    results: list[BenchmarkResult] = []

    for adapter_name, (dumper, loader) in adapters:
        if dumper is None or loader is None:
            continue
        try:
            dumped = _assert_adapter(adapter_name, dumper, loader)
        except Exception as exc:  # noqa: BLE001
            skips.append(f"typeadapter {adapter_name}: conversion failed: {exc}")
            continue

        results.extend(
            [
                measure_sync(
                    adapter_name,
                    "dump",
                    lambda dumper=dumper: dumper.dump(DTO, CreateUser),
                    settings,
                ),
                measure_sync(
                    adapter_name,
                    "load",
                    lambda loader=loader, dumped=dumped: loader.load(
                        dumped,
                        CreateUser,
                    ),
                    settings,
                ),
                measure_sync(
                    adapter_name,
                    "roundtrip",
                    lambda dumper=dumper, loader=loader: loader.load(
                        dumper.dump(DTO, CreateUser),
                        CreateUser,
                    ),
                    settings,
                ),
            ]
        )

    return [*format_results(results), *format_skips(skips)]


def _assert_adapter(name: str, dumper: Dumper, loader: Loader) -> object:
    dumped = dumper.dump(DTO, CreateUser)
    loaded = loader.load(dumped, CreateUser)
    if name == "dummy":
        assert dumped is DTO
        assert loaded is DTO
    else:
        assert loaded == DTO
        assert loader.load(RAW_DTO, CreateUser) == DTO
    return dumped
