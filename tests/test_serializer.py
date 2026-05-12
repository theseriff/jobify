import re
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum, Flag, IntEnum, auto
from fractions import Fraction
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from pathlib import Path
from typing import Generic, NamedTuple, TypeVar
from zoneinfo import ZoneInfo

import pytest

from jobify._internal.serializers.json_extended import SupportedTypes
from jobify.serializers import (
    CBORSerializer,
    ExtendedJSONSerializer,
    JSONSerializer,
    MsgpackSerializer,
    OrjsonSerializer,
    Serializer,
    UnsafePickleSerializer,
)


class EnumTest(Enum):
    VALUE1 = "val1"
    VALUE2 = "val2"


class IntEnumTest(IntEnum):
    LOW = 1
    HIGH = 10


class FlagTest(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()


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


TYPE_REGISTRY = (
    SimpleData,
    NestedData,
    PointDC,
    ComplexDC,
    EnumTest,
    IntEnumTest,
    FlagTest,
)


named_tuple_structures = (
    pytest.param(
        SimpleData(id=1, name="TestA", value=b"10.5"),
        id="SimpleNamedTuple",
    ),
    pytest.param(
        NestedData(key="K1", data=SimpleData(id=2, name="TestB", value=b"")),
        id="NestedNamedTuple",
    ),
    pytest.param(
        (SimpleData(id=3, name="InTuple", value=b"1"), "other_data"),
        id="TupleContainingNamedTuple",
    ),
)

dataclass_structures = (
    pytest.param(PointDC(x=10, y=20, label="origin"), id="SimpleDataclass"),
    pytest.param(
        ComplexDC(id=99, raw_data=b"binary", point=PointDC(x=1, y=2)),
        id="NestedDataclassWithBytes",
    ),
)

date_time_types = (
    pytest.param(date(2024, 6, 15), id="date"),
    pytest.param(date(2000, 1, 1), id="date_y2k"),
    pytest.param(time(14, 30, 15), id="time"),
    pytest.param(time(14, 30, 15, 123456), id="time_with_microseconds"),
    pytest.param(time(0, 0, 0), id="time_midnight"),
)

uuid_types = (
    pytest.param(uuid.UUID("12345678-1234-5678-1234-567812345678"), id="uuid_fixed"),
    pytest.param(uuid.UUID(int=0), id="uuid_nil"),
    pytest.param(uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"), id="uuid_max"),
)

path_types = (
    pytest.param(Path("/usr/bin/python3"), id="path_posix"),
    pytest.param(Path("C:/Users/Admin/AppData"), id="path_windows"),
    pytest.param(Path("relative/path/file.txt"), id="path_relative"),
    pytest.param(Path(), id="path_dot"),
)

numeric_types = (
    pytest.param(Fraction(1, 3), id="fraction_1_3"),
    pytest.param(Fraction(22, 7), id="fraction_22_7"),
    pytest.param(Fraction(0), id="fraction_zero"),
    pytest.param(Fraction(-5, 8), id="fraction_negative"),
    pytest.param(complex(2, 5), id="complex_full"),
    pytest.param(complex(0, 1), id="complex_pure_imaginary"),
    pytest.param(complex(3, 0), id="complex_pure_real"),
    pytest.param(complex(-1, -1), id="complex_negative"),
)

bytearray_types = (
    pytest.param(bytearray(b"mutable_bytes"), id="bytearray"),
    pytest.param(bytearray(b""), id="bytearray_empty"),
    pytest.param(bytearray(range(256)), id="bytearray_all_bytes"),
)

ip_types = (
    pytest.param(IPv4Address("192.168.1.1"), id="ipv4_address"),
    pytest.param(IPv4Address("0.0.0.0"), id="ipv4_address_zero"),  # noqa: S104
    pytest.param(IPv4Address("255.255.255.255"), id="ipv4_address_broadcast"),
    pytest.param(IPv6Address("2001:db8::"), id="ipv6_address"),
    pytest.param(IPv6Address("::1"), id="ipv6_loopback"),
    pytest.param(IPv4Network("192.168.0.0/24"), id="ipv4_network"),
    pytest.param(IPv4Network("10.0.0.0/8"), id="ipv4_network_class_a"),
    pytest.param(IPv6Network("2001:db8::/32"), id="ipv6_network"),
    pytest.param(IPv4Interface("192.168.1.1/24"), id="ipv4_interface"),
    pytest.param(IPv4Interface("10.0.0.1/8"), id="ipv4_interface_class_a"),
    pytest.param(IPv6Interface("2001:db8::1/32"), id="ipv6_interface"),
)

pattern_types = (
    pytest.param(re.compile(r"\d+"), id="pattern_digits"),
    pytest.param(re.compile(r"^[a-z]+$", re.IGNORECASE), id="pattern_ignorecase"),
    pytest.param(
        re.compile(r"(?P<name>\w+)\s+(?P<age>\d+)"), id="pattern_named_groups"
    ),
    pytest.param(
        re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", re.IGNORECASE),
        id="pattern_email",
    ),
    pytest.param(
        re.compile(r"https?://\S+", re.IGNORECASE | re.MULTILINE),
        id="pattern_multi_flags",
    ),
)

enum_subtypes = (
    pytest.param(IntEnumTest.LOW, id="int_enum_low"),
    pytest.param(IntEnumTest.HIGH, id="int_enum_high"),
    pytest.param(FlagTest.READ, id="flag_single"),
    pytest.param(FlagTest.READ | FlagTest.WRITE, id="flag_combined_two"),
    pytest.param(FlagTest.READ | FlagTest.WRITE | FlagTest.EXECUTE, id="flag_all"),
)

collection_types = (
    pytest.param(frozenset({1, 2, 3}), id="frozenset_int"),
    pytest.param(frozenset({"a", "b", "c"}), id="frozenset_str"),
    pytest.param(frozenset(), id="frozenset_empty"),
    pytest.param(deque(["first", "second", "third"]), id="deque_str"),
    pytest.param(deque([1, 2, 3]), id="deque_int"),
    pytest.param(deque(), id="deque_empty"),
)

ordering_regression = (
    pytest.param(
        {
            "dt": datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC")),
            "d": date(2024, 1, 15),
        },
        id="datetime_and_date_coexist",
    ),
    pytest.param(
        [IPv4Address("10.0.0.1"), IPv4Interface("10.0.0.1/24")],
        id="ipv4_address_and_interface_coexist",
    ),
    pytest.param(
        {"plain": b"bytes_value", "mutable": bytearray(b"bytearray_value")},
        id="bytes_and_bytearray_coexist",
    ),
    pytest.param(
        {"mutable": {1, 2, 3}, "immutable": frozenset({1, 2, 3})},
        id="set_and_frozenset_coexist",
    ),
    pytest.param(
        [IPv6Address("2001:db8::1"), IPv6Interface("2001:db8::1/32")],
        id="ipv6_address_and_interface_coexist",
    ),
)


@pytest.mark.parametrize(
    "serializer",
    [
        pytest.param(UnsafePickleSerializer(), id="pickle"),
        pytest.param(ExtendedJSONSerializer(TYPE_REGISTRY), id="ext_json"),
    ],
)
@pytest.mark.parametrize(
    "data",
    [
        # Primitives
        pytest.param(None),
        pytest.param(True),
        pytest.param(False),
        pytest.param(123),
        pytest.param(123.45),
        pytest.param("hello"),
        pytest.param(b"world"),
        # Collections
        pytest.param([1, "a", None, [2, "b", True]]),
        pytest.param((1, "a", None, (2, "b", True))),
        pytest.param({"a": 1, "b": None}),
        pytest.param({1, "a", None}),
        # Stdlib types
        pytest.param(EnumTest.VALUE1, id="Enum"),
        pytest.param(
            datetime(2023, 1, 1, 12, 30, 45, tzinfo=ZoneInfo("UTC")),
            id="Datetime",
        ),
        pytest.param(Decimal("123.456"), id="Decimal"),
        pytest.param(timedelta(days=7), id="timedelta"),
        pytest.param(ZoneInfo("UTC"), id="zoneinfo"),
        # Custom types
        *named_tuple_structures,
        *dataclass_structures,
        # New types
        *date_time_types,
        *uuid_types,
        *path_types,
        *numeric_types,
        *bytearray_types,
        *ip_types,
        *pattern_types,
        *enum_subtypes,
        *collection_types,
        *ordering_regression,
    ],
)
def test_serialization_extended(
    serializer: Serializer,
    data: SupportedTypes,
) -> None:
    serialized = serializer.dumpb(data)
    deserialized = serializer.loadb(serialized)
    assert deserialized == data


@pytest.mark.parametrize(
    "serializer",
    [
        pytest.param(JSONSerializer(), id="json"),
        pytest.param(CBORSerializer(), id="cbor"),
        pytest.param(OrjsonSerializer(), id="orjson"),
        pytest.param(MsgpackSerializer(), id="msgpack"),
    ],
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
class JobContext:
    task_id: str


@dataclass(slots=True, kw_only=True, frozen=True)
class GenericComplexDC(Generic[T]):
    id: int
    data: T


@dataclass(slots=True, kw_only=True, frozen=True)
class SimpleType:
    name: str


def test_registry_types_coverage() -> None:
    serializer = ExtendedJSONSerializer()

    serializer.register_hints([JobContext])
    assert "JobContext" not in serializer.registry

    serializer.register_hints([GenericComplexDC[SimpleType]])
    assert "GenericComplexDC" not in serializer.registry
    assert "SimpleType" in serializer.registry
    assert serializer.registry["SimpleType"] is SimpleType

    serializer.register_hints([int])
    assert "int" not in serializer.registry

    initial_len = len(serializer.registry)
    serializer.register_hints([SimpleType])
    assert len(serializer.registry) == initial_len
