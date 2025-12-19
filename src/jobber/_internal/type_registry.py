# ruff: noqa: ANN401
from collections.abc import Iterable
from dataclasses import is_dataclass
from typing import Any, get_args, get_type_hints


def is_named_tuple_type(tp: Any) -> bool:
    return (
        isinstance(tp, type)
        and issubclass(tp, tuple)
        and hasattr(tp, "_fields")  # pyright: ignore[reportUnknownArgumentType]
    )


def is_structured_type(tp: Any) -> bool:
    return is_dataclass(tp) or is_named_tuple_type(tp)


def collect_structured_types(
    types: Iterable[Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    registry = {}

    for tp in types:
        if not is_structured_type(tp):
            continue
        if getattr(tp, "__name__", None) == "JobContext":
            continue
        if args := get_args(tp):
            _ = collect_structured_types(args, registry)
            continue
        if tp.__name__ in registry:
            continue

        registry[tp.__name__] = tp
        field_hints = get_type_hints(tp)
        _ = collect_structured_types(field_hints.values(), registry)

    return registry
