from dataclasses import dataclass
from typing import NamedTuple

from benchmarks.common import (
    BenchmarkResult,
    BenchmarkSettings,
    format_results,
    format_skips,
    measure_sync,
)
from benchmarks.registry import configure_extended_types, iter_available_serializers
from jobify._internal.serializers.json_extended import SupportedTypes
from jobify.serializers import Serializer


@dataclass(frozen=True, slots=True)
class BenchDataclass:
    id: int
    name: str
    tags: list[str]
    meta: dict[str, int]


@dataclass(frozen=True, slots=True)
class NestedBenchDataclass:
    bench: BenchDataclass


class BenchNamedTuple(NamedTuple):
    x: float
    y: float
    label: str


JSON_PAYLOAD: dict[str, SupportedTypes] = {
    "none_value": None,
    "boolean_true": True,
    "boolean_false": False,
    "positive_int": 42,
    "negative_int": -15,
    "positive_float": 3.14159,
    "unicode_string": "Привет, мир! 🌍",
    "simple_list": [1, 2, 3, 4, 5],
    "mixed_list": [None, True, 42, 3.14, "text"],
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
                "id": idx,
                "name": f"user_{idx}",
                "tags": ["admin", "moderator"] if idx % 2 else ["user"],
                "scores": [95, 87, 92],
                "metadata": {"created_at": "2023-01-01", "is_verified": True},
            }
            for idx in range(50)
        ],
        "system_info": {
            "version": 2.1,
            "features": ["auth", "logging", "api"],
            "config": {"debug": True, "max_connections": 100, "timeout": 30.5},
        },
    },
    "unicode_data": {
        "emojis": "😀 🎉 🌟 📚 💻",
        "special_chars": "Line1\nLine2\tTabbed\\Backslash",
        "unicode_mix": "Hello 世界 🌍 Привет",
    },
}

EXTENDED_PAYLOAD: dict[str, SupportedTypes] = {
    **JSON_PAYLOAD,
    "binary_data": b"binary_data_bytes",
    "simple_set": {1, 2, 3, 4, 5},
    "simple_tuple": (1, "two", 3.0, None),
    "coordinates": [
        (40.7128, -74.0060),
        (51.5074, -0.1278),
        (35.6762, 139.6503),
    ],
    "custom_types": {
        "dataclasses_simple": BenchDataclass(1, "test", ["a"], {"x": 1}),
        "namedtuples_simple": BenchNamedTuple(1.1, 2.2, "point"),
        "dataclasses_list": [BenchDataclass(i, f"nm_{i}", [], {}) for i in range(20)],
        "mixed_custom": {
            "dc": BenchDataclass(99, "nested", ["root"], {}),
            "nt": BenchNamedTuple(0.0, 0.0, "origin"),
            "nested_dc": NestedBenchDataclass(
                BenchDataclass(99, "nested", ["root"], {}),
            ),
        },
    },
}

PAYLOADS = {
    "json": JSON_PAYLOAD,
    "extended": EXTENDED_PAYLOAD,
}

configure_extended_types((BenchDataclass, NestedBenchDataclass, BenchNamedTuple))


def serializers_measure() -> list[str]:
    settings = BenchmarkSettings.from_env(
        prefix="JOBIFY_BENCH_SERIALIZER",
        warmup=2,
        rounds=5,
        iterations=200,
    )
    results: list[BenchmarkResult] = []
    skips: list[str] = []

    for payload_name, payload in PAYLOADS.items():
        serializers, current_skips = iter_available_serializers(payload_name)
        skips.extend(current_skips)
        for serializer_name, serializer in serializers:
            case_name = f"{serializer_name}/{payload_name}"
            try:
                encoded = _assert_roundtrip(serializer, payload)
            except Exception as exc:  # noqa: BLE001
                skips.append(f"serializer {case_name}: roundtrip failed: {exc}")
                continue

            results.extend(
                [
                    measure_sync(
                        case_name,
                        "dump",
                        lambda serializer=serializer, payload=payload: serializer.dumpb(
                            payload,
                        ),
                        settings,
                        size_bytes=len(encoded),
                    ),
                    measure_sync(
                        case_name,
                        "load",
                        lambda serializer=serializer, encoded=encoded: serializer.loadb(
                            encoded,
                        ),
                        settings,
                        size_bytes=len(encoded),
                    ),
                    measure_sync(
                        case_name,
                        "roundtrip",
                        lambda serializer=serializer, payload=payload: serializer.loadb(
                            serializer.dumpb(payload),
                        ),
                        settings,
                        size_bytes=len(encoded),
                    ),
                ]
            )

    return [*format_results(results), *format_skips(skips)]


def _assert_roundtrip(serializer: Serializer, payload: object) -> bytes:
    encoded = serializer.dumpb(payload)
    decoded = serializer.loadb(encoded)
    assert decoded == payload
    return encoded
