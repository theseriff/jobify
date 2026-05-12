from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias, cast

from adaptix import Retort

from jobify._internal.typeadapter.base import Dumper, Loader

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Sequence
from jobify._internal.typeadapter.dummy import DummyDumper, DummyLoader
from jobify.serializers import (
    CBORSerializer,
    ExtendedJSONSerializer,
    JSONSerializer,
    MsgpackSerializer,
    OrjsonSerializer,
    Serializer,
    UnsafePickleSerializer,
)
from jobify.typeadapter import PydanticConverter

PayloadKind: TypeAlias = Literal["json", "extended"]
TypeAdapterPair: TypeAlias = tuple[Dumper | None, Loader | None]


@dataclass(frozen=True, slots=True)
class SerializerBenchCase:
    name: str
    factory: Callable[[], Serializer]
    payloads: frozenset[PayloadKind] = frozenset({"json"})

    def build(self) -> Serializer:
        return self.factory()


@dataclass(frozen=True, slots=True)
class TypeAdapterBenchCase:
    name: str
    factory: Callable[[], TypeAdapterPair]
    jobify_enabled: bool = True

    def build(self) -> TypeAdapterPair:
        return self.factory()


SERIALIZER_CASES: tuple[SerializerBenchCase, ...] = (
    SerializerBenchCase("json", JSONSerializer),
    SerializerBenchCase("orjson", OrjsonSerializer),
    SerializerBenchCase("msgpack", MsgpackSerializer),
    SerializerBenchCase("cbor", CBORSerializer),
    SerializerBenchCase(
        "pickle",
        UnsafePickleSerializer,
        frozenset({"json", "extended"}),
    ),
    SerializerBenchCase(
        "extended_json",
        lambda: ExtendedJSONSerializer(_EXTENDED_TYPES),
        frozenset({"extended"}),
    ),
)

TYPE_ADAPTER_CASES: tuple[TypeAdapterBenchCase, ...] = (
    TypeAdapterBenchCase("none", lambda: (None, None)),
    TypeAdapterBenchCase(
        "dummy",
        lambda: (DummyDumper(), DummyLoader()),
        jobify_enabled=False,
    ),
    TypeAdapterBenchCase("adaptix", lambda: _same_adapter(Retort())),
    TypeAdapterBenchCase("pydantic", lambda: _same_adapter(PydanticConverter())),
)

_EXTENDED_TYPES: tuple[type[Hashable], ...] = ()


def configure_extended_types(types: Sequence[type[Hashable]]) -> None:
    global _EXTENDED_TYPES  # noqa: PLW0603
    _EXTENDED_TYPES = tuple(types)


def iter_available_serializers(
    payload: PayloadKind,
) -> tuple[list[tuple[str, Serializer]], list[str]]:
    serializers: list[tuple[str, Serializer]] = []
    skips: list[str] = []
    for case in SERIALIZER_CASES:
        if payload not in case.payloads:
            continue
        try:
            serializers.append((case.name, case.build()))
        except ImportError as exc:
            skips.append(f"serializer {case.name}: {exc}")
    return serializers, skips


def iter_available_type_adapters(
    *,
    include_jobify_disabled: bool = False,
) -> tuple[list[tuple[str, TypeAdapterPair]], list[str]]:
    adapters: list[tuple[str, TypeAdapterPair]] = []
    skips: list[str] = []
    for case in TYPE_ADAPTER_CASES:
        if not include_jobify_disabled and not case.jobify_enabled:
            continue
        try:
            adapters.append((case.name, case.build()))
        except ImportError as exc:
            skips.append(f"typeadapter {case.name}: {exc}")
    return adapters, skips


def _same_adapter(adapter: Dumper | Loader) -> TypeAdapterPair:
    return cast("TypeAdapterPair", (adapter, adapter))
