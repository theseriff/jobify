from __future__ import annotations

import base64
import dataclasses
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from collections.abc import Callable
from typing import Any, ClassVar, Protocol, TypeAlias

from typing_extensions import TypeIs


class DataclassType(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]


class NamedTupleType(Protocol):
    _asdict: ClassVar[Callable[[NamedTupleType], dict[str, SerializableTypes]]]


SerializableTypes: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | bytes
    | DataclassType
    | NamedTupleType
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
TypeRegistry: TypeAlias = dict[str, Callable[..., SerializableTypes]]


class JobsSerializer(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def dumpb(self, data: SerializableTypes) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def loadb(self, data: bytes) -> SerializableTypes:
        raise NotImplementedError


def is_dataclass(o: SerializableTypes) -> TypeIs[DataclassType]:
    return dataclasses.is_dataclass(o) and not isinstance(o, type)


def is_named_tuple(o: SerializableTypes) -> TypeIs[NamedTupleType]:
    return isinstance(o, tuple) and hasattr(o, "_asdict")


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


def json_extended_encoder(o: SerializableTypes) -> JsonCompat:  # noqa: PLR0911
    if is_dataclass(o):  # pragma: no cover
        if params := getattr(o.__class__, "__dataclass_params__", {}):
            params = {
                param: flag
                for param in _DATACLASS_PARAMS
                if (flag := getattr(params, param, None))
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
    if is_named_tuple(o):
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


class JsonDecoderHook:
    def __init__(self, registry: TypeRegistry) -> None:
        self.registry: TypeRegistry = registry

    def __call__(self, dct: dict[str, Any]) -> SerializableTypes:  # noqa: PLR0911
        if "__dataclass__" in dct:
            data = dct["__dataclass__"]
            fields = data["fields"]
            type_name = data["type"]
            if cls := self.registry.get(type_name):
                return cls(**fields)
            dc_cls = dataclasses.make_dataclass(
                type_name,
                fields.keys(),
                **data["params"],
            )
            return self.registry.setdefault(type_name, dc_cls)(**fields)

        if "__namedtuple__" in dct:
            data = dct["__namedtuple__"]
            fields = data["fields"]
            type_name = data["type"]
            if cls := self.registry.get(type_name):
                return cls(**fields)
            nt_cls = namedtuple(type_name, fields.keys())  # type:ignore[misc]  # noqa: PYI024 # pyright: ignore[reportUntypedNamedTuple]
            return self.registry.setdefault(type_name, nt_cls)(**fields)

        if "__bytes__" in dct:
            return base64.b64decode(dct["__bytes__"])
        if "__tuple__" in dct:
            return tuple(dct["__tuple__"])
        if "__set__" in dct:
            return set(dct["__set__"])
        return dct
