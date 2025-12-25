from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, NamedTuple, TypeVar
from zoneinfo import ZoneInfo

import pytest

from jobber._internal.serializers.json_extended import SupportedTypes
from jobber.serializers import (
    ExtendedJSONSerializer,
    JSONSerializer,
    Serializer,
    UnsafePickleSerializer,
)


class EnumTest(Enum):
    VALUE1 = "val1"
    VALUE2 = "val2"


class SimpleData(NamedTuple):
    id: int
    name: str
    value: bytes


class NestedData(NamedTuple):
    key: str
    data: SimpleData


@dataclass(slots=True, kw_only=True, frozen=True)
class PointDC:
    x: int
    y: int
    label: str | None = None


@dataclass(slots=True, kw_only=True, frozen=True)
class ComplexDC:
    id: int
    raw_data: bytes
    point: PointDC


type_registry: dict[str, Any] = {
    "SimpleData": SimpleData,
    "NestedData": NestedData,
    "PointDC": PointDC,
    "ComplexDC": ComplexDC,
    "EnumTest": EnumTest,
}


named_tuple_structures = (
    pytest.param(
        SimpleData(id=1, name="TestA", value=b"10.5"),
        id="SimpleNamedTuple",
    ),
    pytest.param(
        NestedData(
            key="K1",
            data=SimpleData(id=2, name="TestB", value=b""),
        ),
        id="NestedNamedTuple",
    ),
    pytest.param(
        (SimpleData(id=3, name="InTuple", value=b"1"), "other_data"),
        id="TupleContainingNamedTuple",
    ),
)
dataclass_structures = (
    pytest.param(
        PointDC(x=10, y=20, label="origin"),
        id="SimpleDataclass",
    ),
    pytest.param(
        ComplexDC(id=99, raw_data=b"binary", point=PointDC(x=1, y=2)),
        id="NestedDataclassWithBytes",
    ),
)


@pytest.mark.parametrize(
    "serializer",
    [
        pytest.param(UnsafePickleSerializer(), id="pickle"),
        pytest.param(ExtendedJSONSerializer(type_registry), id="ext_json"),
    ],
)
@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None),
        pytest.param(True),
        pytest.param(False),
        pytest.param(123),
        pytest.param(123.45),
        pytest.param("hello"),
        pytest.param(b"world"),
        pytest.param([1, "a", None, [2, "b", True]]),
        pytest.param((1, "a", None, (2, "b", True))),
        pytest.param({"a": 1, "b": None}),
        pytest.param({1, "a", None}),
        pytest.param(EnumTest.VALUE1, id="Enum"),
        pytest.param(
            datetime(2023, 1, 1, 12, 30, 45, tzinfo=ZoneInfo("UTC")),
            id="Datetime",
        ),
        pytest.param(Decimal("123.456"), id="Decimal"),
        *named_tuple_structures,
        *dataclass_structures,
    ],
)
def test_serialization_extended(
    serializer: Serializer,
    data: SupportedTypes,
) -> None:
    """Tests that all serializers can [de]serialize basic Python types."""
    serialized = serializer.dumpb(data)
    deserialized = serializer.loadb(serialized)
    assert deserialized == data


@pytest.mark.parametrize(
    "serializer",
    [pytest.param(JSONSerializer(), id="json")],
)
@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            {
                "0": None,
                "1": True,
                "2": False,
                "3": 123,
                "4": 123.45,
                "5": "hello",
                "7": [1, "a", None, [2, "b", True]],
                "8": {"a": 1, "b": None},
            }
        )
    ],
)
def test_serialization_simple(
    serializer: Serializer,
    data: SupportedTypes,
) -> None:
    """Tests that all serializers can [de]serialize basic Python types."""
    serialized = serializer.dumpb(data)
    deserialized = serializer.loadb(serialized)
    assert deserialized == data


T = TypeVar("T")


@dataclass(slots=True, kw_only=True, frozen=True)
class JobContext:  # This will trigger the JobContext check
    task_id: str


@dataclass(slots=True, kw_only=True, frozen=True)
class GenericComplexDC(Generic[T]):  # This will trigger the get_args check
    id: int
    data: T  # This will be the generic part


@dataclass(slots=True, kw_only=True, frozen=True)
class SimpleType:  # A simple dataclass to be registered
    name: str


def test_registry_types_coverage() -> None:
    serializer = ExtendedJSONSerializer()

    # Test JobContext skip
    serializer.registry_types([JobContext])
    assert "JobContext" not in serializer.registry

    # Test generic structured type handling
    serializer.registry_types([GenericComplexDC[SimpleType]])
    assert "GenericComplexDC" not in serializer.registry
    assert "SimpleType" in serializer.registry
    assert serializer.registry["SimpleType"] is SimpleType

    # Test a non-structured type, should be skipped
    serializer.registry_types([int])
    assert "int" not in serializer.registry

    # Test an already registered type
    initial_len = len(serializer.registry)
    serializer.registry_types([SimpleType])
    assert (
        len(serializer.registry) == initial_len
    )  # Should not re-register, length unchanged
