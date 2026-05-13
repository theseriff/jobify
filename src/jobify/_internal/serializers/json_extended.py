from __future__ import annotations

import base64
import dataclasses
import json
import re
import uuid
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
    ip_address,
    ip_interface,
    ip_network,
)
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    NamedTuple,
    Protocol,
    TypeAlias,
    get_args,
    get_type_hints,
)
from zoneinfo import ZoneInfo

from typing_extensions import TypeIs, override

from jobify._internal.serializers.base import JSONCompat, Serializer


class DataclassType(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]


SupportedTypes: TypeAlias = (
    None
    | int
    | str
    | bool
    | float
    | Enum
    | bytes
    | bytearray
    | Decimal
    | Fraction
    | ZoneInfo
    | datetime
    | date
    | time
    | timedelta
    | uuid.UUID
    | complex
    | Path
    | IPv4Address
    | IPv6Address
    | IPv4Network
    | IPv6Network
    | IPv4Interface
    | IPv6Interface
    | re.Pattern[str]
    | DataclassType
    | frozenset["SupportedTypes"]
    | set["SupportedTypes"]
    | deque["SupportedTypes"]
    | list["SupportedTypes"]
    | tuple["SupportedTypes", ...]
    | dict[str, "SupportedTypes"]
)
TypeRegistry: TypeAlias = dict[str, Callable[..., SupportedTypes]]


def is_named_tuple_type(tp: Any) -> TypeIs[NamedTuple]:  # noqa: ANN401
    return isinstance(tp, type) and issubclass(tp, tuple) and hasattr(tp, "_fields")


def is_named_tuple(o: SupportedTypes) -> TypeIs[NamedTuple]:
    return isinstance(o, tuple) and hasattr(o, "_asdict")


def is_dataclass(o: SupportedTypes) -> TypeIs[DataclassType]:
    return dataclasses.is_dataclass(o) and not isinstance(o, type)


def is_structured_type(tp: Any) -> bool:  # noqa: ANN401
    return (
        dataclasses.is_dataclass(tp)
        or is_named_tuple_type(tp)
        or (hasattr(tp, "__origin__") and dataclasses.is_dataclass(tp.__origin__))
    )


def json_extended_encoder(o: SupportedTypes) -> JSONCompat:  # noqa: C901, PLR0911, PLR0912
    if is_dataclass(o):
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
                "fields": {k: json_extended_encoder(v) for k, v in o._asdict().items()},
            }
        }
    if isinstance(o, Enum):
        return {"__enum__": {"type": o.__class__.__name__, "value": o.value}}
    if isinstance(o, datetime):
        return {"__datetime__": o.isoformat()}
    if isinstance(o, date):
        return {"__date__": o.isoformat()}
    if isinstance(o, time):
        return {"__time__": o.isoformat()}
    if isinstance(o, timedelta):
        return {"__timedelta__": o.total_seconds()}
    if isinstance(o, Decimal):
        return {"__decimal__": str(o)}
    if isinstance(o, Fraction):
        return {"__fraction__": str(o)}
    if isinstance(o, complex):
        return {"__complex__": [o.real, o.imag]}
    if isinstance(o, uuid.UUID):
        return {"__uuid__": str(o)}
    if isinstance(o, Path):
        return {"__path__": o.as_posix()}
    if isinstance(o, (IPv4Interface, IPv6Interface)):
        return {"__ipinterface__": str(o)}
    if isinstance(o, (IPv4Address, IPv6Address)):
        return {"__ipaddress__": str(o)}
    if isinstance(o, (IPv4Network, IPv6Network)):
        return {"__ipnetwork__": str(o)}
    if isinstance(o, re.Pattern):
        return {"__pattern__": {"pattern": o.pattern, "flags": o.flags}}
    if isinstance(o, bytearray):
        return {"__bytearray__": base64.b64encode(bytes(o)).decode("utf-8")}
    if isinstance(o, bytes):
        return {"__bytes__": base64.b64encode(o).decode("utf-8")}
    if isinstance(o, ZoneInfo):
        return {"__zoneinfo__": o.key}
    if isinstance(o, frozenset):
        return {"__frozenset__": [json_extended_encoder(item) for item in o]}
    if isinstance(o, set):
        return {"__set__": [json_extended_encoder(item) for item in o]}
    if isinstance(o, deque):
        return {"__deque__": [json_extended_encoder(item) for item in o]}
    if isinstance(o, list):
        return [json_extended_encoder(item) for item in o]
    if isinstance(o, tuple):
        return {"__tuple__": [json_extended_encoder(item) for item in o]}
    if isinstance(o, dict):
        return {k: json_extended_encoder(v) for k, v in o.items()}
    return o


class JsonDecoderHook:
    def __init__(self, registry: TypeRegistry) -> None:
        self.registry: TypeRegistry = registry

    def __call__(self, dct: dict[str, Any]) -> SupportedTypes:  # noqa: C901, PLR0911, PLR0912
        if "__dataclass__" in dct:
            data = dct["__dataclass__"]
            return self.registry[data["type"]](**data["fields"])
        if "__namedtuple__" in dct:
            data = dct["__namedtuple__"]
            return self.registry[data["type"]](**data["fields"])
        if "__enum__" in dct:
            data = dct["__enum__"]
            return self.registry[data["type"]](data["value"])
        if "__datetime__" in dct:
            return datetime.fromisoformat(dct["__datetime__"])
        if "__date__" in dct:
            return date.fromisoformat(dct["__date__"])
        if "__time__" in dct:
            return time.fromisoformat(dct["__time__"])
        if "__timedelta__" in dct:
            return timedelta(seconds=dct["__timedelta__"])
        if "__decimal__" in dct:
            return Decimal(dct["__decimal__"])
        if "__fraction__" in dct:
            return Fraction(dct["__fraction__"])
        if "__complex__" in dct:
            real, imag = dct["__complex__"]
            return complex(real, imag)
        if "__uuid__" in dct:
            return uuid.UUID(dct["__uuid__"])
        if "__path__" in dct:
            return Path(dct["__path__"])
        if "__ipinterface__" in dct:
            return ip_interface(dct["__ipinterface__"])
        if "__ipaddress__" in dct:
            return ip_address(dct["__ipaddress__"])
        if "__ipnetwork__" in dct:
            return ip_network(dct["__ipnetwork__"])
        if "__pattern__" in dct:
            data = dct["__pattern__"]
            return re.compile(data["pattern"], data["flags"])
        if "__bytearray__" in dct:
            return bytearray(base64.b64decode(dct["__bytearray__"]))
        if "__bytes__" in dct:
            return base64.b64decode(dct["__bytes__"])
        if "__zoneinfo__" in dct:
            return ZoneInfo(dct["__zoneinfo__"])
        if "__frozenset__" in dct:
            return frozenset(dct["__frozenset__"])
        if "__set__" in dct:
            return set(dct["__set__"])
        if "__deque__" in dct:
            return deque(dct["__deque__"])
        if "__tuple__" in dct:
            return tuple(dct["__tuple__"])
        return dct


class ExtendedJSONSerializer(Serializer):
    def __init__(
        self,
        registry: Sequence[Callable[..., SupportedTypes]] = (),
    ) -> None:
        self.registry: TypeRegistry = {}
        self.add_system_types(registry)
        self.decoder_hook: JsonDecoderHook = JsonDecoderHook(self.registry)

    def add_system_types(self, tp: Sequence[Callable[..., SupportedTypes]], /) -> None:
        self.registry.update({t.__name__: t for t in tp})

    @override
    def dumpb(self, data: SupportedTypes) -> bytes:
        return json.dumps(json_extended_encoder(data)).encode("utf-8")

    @override
    def loadb(self, data: bytes) -> SupportedTypes:
        r: SupportedTypes = json.loads(data, object_hook=self.decoder_hook)
        return r

    def register_hints(self, types: Iterable[Any]) -> None:
        for tp in types:
            if not is_structured_type(tp):
                continue
            if getattr(tp, "__name__", None) == "JobContext":
                continue
            if args := get_args(tp):
                self.register_hints(args)
                continue
            if tp.__name__ in self.registry:
                continue
            self.registry[tp.__name__] = tp
            self.register_hints(get_type_hints(tp).values())
