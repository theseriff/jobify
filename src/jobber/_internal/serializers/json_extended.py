from __future__ import annotations

import base64
import dataclasses
import json
from collections.abc import Callable, Iterable
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar, Protocol, TypeAlias, get_args, get_type_hints

from typing_extensions import TypeIs, override

from jobber._internal.serializers.base import JSONCompat, Serializer


class DataclassType(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]


class NamedTupleType(Protocol):
    _asdict: ClassVar[Callable[[NamedTupleType], dict[str, SupportedTypes]]]


SupportedTypes: TypeAlias = (
    None
    | int
    | str
    | bool
    | Enum
    | float
    | bytes
    | Decimal
    | datetime
    | DataclassType
    | NamedTupleType
    | set["SupportedTypes"]
    | list["SupportedTypes"]
    | tuple["SupportedTypes", ...]
    | dict[str, "SupportedTypes"]
)
TypeRegistry: TypeAlias = dict[str, Callable[..., SupportedTypes]]


def is_named_tuple_type(tp: Any) -> bool:  # noqa: ANN401
    return (
        isinstance(tp, type)
        and issubclass(tp, tuple)
        and hasattr(tp, "_fields")  # pyright: ignore[reportUnknownArgumentType]
    )


def is_named_tuple(o: SupportedTypes) -> TypeIs[NamedTupleType]:
    return isinstance(o, tuple) and hasattr(o, "_asdict")


def is_dataclass(o: SupportedTypes) -> TypeIs[DataclassType]:
    return dataclasses.is_dataclass(o) and not isinstance(o, type)


def is_structured_type(tp: Any) -> bool:  # noqa: ANN401
    return (
        dataclasses.is_dataclass(tp)
        or is_named_tuple_type(tp)
        or (
            hasattr(tp, "__origin__")
            and dataclasses.is_dataclass(tp.__origin__)
        )
    )


def json_extended_encoder(o: SupportedTypes) -> JSONCompat:  # noqa: C901, PLR0911
    if is_dataclass(o):  # pragma: no cover
        return {
            "__dataclass__": {
                "type": o.__class__.__name__,
                "fields": {
                    f.name: json_extended_encoder(getattr(o, f.name))
                    for f in dataclasses.fields(o)
                },
            }
        }
    if is_named_tuple(o):
        return {
            "__namedtuple__": {
                "type": o.__class__.__name__,
                "fields": {
                    k: json_extended_encoder(v) for k, v in o._asdict().items()
                },
            }
        }
    if isinstance(o, Enum):
        return {
            "__enum__": {
                "type": o.__class__.__name__,
                "value": o.value,
            }
        }
    if isinstance(o, datetime):
        return {"__datetime__": o.isoformat()}
    if isinstance(o, Decimal):
        return {"__decimal__": str(o)}
    if isinstance(o, tuple):
        return {"__tuple__": [json_extended_encoder(item) for item in o]}
    if isinstance(o, set):
        return {"__set__": [json_extended_encoder(item) for item in o]}
    if isinstance(o, list):
        return [json_extended_encoder(item) for item in o]
    if isinstance(o, dict):
        return {k: json_extended_encoder(v) for k, v in o.items()}
    if isinstance(o, bytes):
        return {"__bytes__": base64.b64encode(o).decode("utf-8")}
    return o


class JsonDecoderHook:
    def __init__(self, registry: TypeRegistry) -> None:
        self.registry: TypeRegistry = registry

    def __call__(self, dct: dict[str, Any]) -> SupportedTypes:  # noqa: PLR0911
        if "__dataclass__" in dct:
            data = dct["__dataclass__"]
            fields = data["fields"]
            type_name = data["type"]
            return self.registry[type_name](**fields)

        if "__namedtuple__" in dct:
            data = dct["__namedtuple__"]
            fields = data["fields"]
            type_name = data["type"]
            return self.registry[type_name](**fields)

        if "__enum__" in dct:
            data = dct["__enum__"]
            type_name = data["type"]
            return self.registry[type_name](data["value"])

        if "__datetime__" in dct:
            return datetime.fromisoformat(dct["__datetime__"])
        if "__decimal__" in dct:
            return Decimal(dct["__decimal__"])
        if "__bytes__" in dct:
            return base64.b64decode(dct["__bytes__"])
        if "__tuple__" in dct:
            return tuple(dct["__tuple__"])
        if "__set__" in dct:
            return set(dct["__set__"])
        return dct


class ExtendedJSONSerializer(Serializer):
    def __init__(self, registry: TypeRegistry | None = None) -> None:
        self.registry: TypeRegistry = registry or {}
        self.decoder_hook: JsonDecoderHook = JsonDecoderHook(self.registry)

    @override
    def dumpb(self, data: SupportedTypes) -> bytes:
        json_compat = json_extended_encoder(data)
        return json.dumps(json_compat).encode("utf-8")

    @override
    def loadb(self, data: bytes) -> SupportedTypes:
        decoded: SupportedTypes = json.loads(
            data,
            object_hook=self.decoder_hook,
        )
        return decoded

    def registry_types(self, types: Iterable[Any]) -> None:
        for tp in types:
            if not is_structured_type(tp):
                continue
            if getattr(tp, "__name__", None) == "JobContext":
                continue
            if args := get_args(tp):
                self.registry_types(args)
                continue
            if tp.__name__ in self.decoder_hook.registry:
                continue

            self.registry[tp.__name__] = tp
            field_hints = get_type_hints(tp)
            self.registry_types(field_hints.values())
