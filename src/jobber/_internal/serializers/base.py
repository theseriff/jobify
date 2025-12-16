from __future__ import annotations

import base64
import dataclasses
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from typing import (
    TYPE_CHECKING,
    Any,
    NamedTuple,
    Protocol,
    TypeAlias,
    TypeGuard,
    cast,
)

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

SerializableTypes: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | bytes
    | set["SerializableTypes"]
    | list["SerializableTypes"]
    | tuple["SerializableTypes", ...]
    | dict[str, "SerializableTypes"]
)

JsonCompat: TypeAlias = (
    dict[str, "JsonCompat"]
    | list["JsonCompat"]
    | str
    | int
    | float
    | bool
    | None
)


class JobsSerializer(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def dumpb(self, data: SerializableTypes) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def loadb(self, data: bytes) -> SerializableTypes:
        raise NotImplementedError


_DATACLASS_PARAMS = (
    "eq",
    "frozen",
    "init",
    "kw_only",
    "match_args",
    "order",
    "repr",
    "slots",
    "unsafe_hash",
    "weakref_slot",
)


def guard_is_dataclass(o: SerializableTypes) -> TypeGuard[DataclassInstance]:
    return dataclasses.is_dataclass(o) and not isinstance(o, type)  # type: ignore[unreachable]


def json_extended_encoder(o: SerializableTypes) -> JsonCompat:  # noqa: PLR0911
    if guard_is_dataclass(o):  # pragma: no cover
        if params := getattr(o.__class__, "__dataclass_params__", {}):
            params = {
                field: getattr(params, field) for field in _DATACLASS_PARAMS
            }

        return {
            "__dataclass__": {
                "type": o.__class__.__name__,
                "params": params,
                "fields": {
                    f.name: json_extended_encoder(getattr(o, f.name))
                    for f in dataclasses.fields(o)
                },
            }
        }
    if isinstance(o, tuple) and hasattr(o, "_asdict"):
        o = cast("NamedTuple", o)
        return {
            "__namedtuple__": {
                "type": o.__class__.__name__,
                "fields": {
                    k: json_extended_encoder(v) for k, v in o._asdict().items()
                },
            }
        }
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


def json_extended_decoder(dct: dict[str, Any]) -> SerializableTypes:
    if "__dataclass__" in dct:
        data = dct["__dataclass__"]
        params = data["params"]
        type_name = data["type"]
        fields_data = data["fields"]
        dc_cls = dataclasses.make_dataclass(
            type_name,
            fields_data.keys(),
            **params,
        )
        r: SerializableTypes = dc_cls(**fields_data)
        return r

    if "__namedtuple__" in dct:
        data = dct["__namedtuple__"]
        type_name = data["type"]
        fields = data["fields"]
        nt_cls = namedtuple(type_name, fields.keys())  # type:ignore[misc]  # noqa: PYI024 # pyright: ignore[reportUntypedNamedTuple]
        return nt_cls(**fields)

    if "__bytes__" in dct:
        return base64.b64decode(dct["__bytes__"])
    if "__tuple__" in dct:
        return tuple(dct["__tuple__"])
    if "__set__" in dct:
        return set(dct["__set__"])
    return dct
