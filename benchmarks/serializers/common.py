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
)
from pathlib import Path
from typing import Any, NamedTuple, Protocol, TypeVar, cast
from zoneinfo import ZoneInfo

import pytest
from adaptix import Retort
from typing_extensions import override

from jobify._internal.common.constants import UNSET
from jobify.serializers import Serializer
from jobify.typeadapter import Dumper, Loader, PydanticConverter


class PairAdapter(Dumper, Loader, Protocol):
    pass


benchmark_serializer = pytest.mark.benchmark(group="serializers")
parametrize_adapters = pytest.mark.parametrize(
    "adapter",
    [
        pytest.param(Retort(), id="adaptix"),
        pytest.param(PydanticConverter(), id="pydantic"),
    ],
)


@dataclass
class BenchDataclass:
    id: int
    name: str
    tags: list[str]
    meta: dict[str, int]


@dataclass
class NestedBenchDataclass:
    bench: BenchDataclass


class BenchNamedTuple(NamedTuple):
    x: float
    y: float
    label: str


class Status(Enum):
    PENDING = "pending"
    ACTIVE = "active"


class Priority(IntEnum):
    LOW = 1
    HIGH = 10


class Permissions(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()


@dataclass
class BenchData:
    # --- Primitives ---
    none_value: None
    bool_true: bool
    bool_false: bool
    pos_int: int
    neg_int: int
    large_int: int  # 10**18
    pos_float: float
    neg_float: float
    float_precision: float  # 0.1 + 0.2 edge case
    string: str
    empty_string: str
    unicode_string: str
    binary: bytes
    empty_bytes: bytes

    # --- Sequences ---
    int_list: list[int]
    nested_list: list[list[int]]
    mixed_tuple: tuple[None, bool, int, float, str, bytes]
    int_tuple: tuple[int, int, int]
    heterogeneous_tuple: tuple[int, str, float, None]
    bytes_tuple: tuple[bytes, bytes]
    empty_tuple: tuple[()]

    # --- Sets ---
    int_set: set[int]
    str_set: set[str]
    frozenset_int: frozenset[int]

    # --- Mappings ---
    simple_dict: dict[str, int | str | bool]
    nested_dict: dict[str, Any]

    # --- Mixed collections ---
    list_of_sets: list[set[int]]
    tuple_of_lists: tuple[list[int], list[int], list[int]]

    # --- Custom dataclasses / NamedTuples ---
    simple_dc: BenchDataclass
    dc_list: list[BenchDataclass]
    nested_dc: NestedBenchDataclass
    named_tuple: BenchNamedTuple

    # --- Enums ---
    str_enum: Status
    int_enum: Priority
    flag_enum: Permissions

    # --- UUID ---
    uuid_v4: uuid.UUID
    uuid_v1: uuid.UUID

    # --- Date / time ---
    datetime_utc: datetime
    datetime_tz: datetime
    date_val: date
    time_val: time
    timedelta_val: timedelta

    # --- Numeric ---
    decimal_val: Decimal
    fraction_val: Fraction
    complex_val: complex

    # --- Paths ---
    posix_path: Path
    windows_path: Path

    # --- IP / network ---
    ipv4: IPv4Address
    ipv6: IPv6Address
    ipv4_network: IPv4Network
    ipv4_interface: IPv4Interface
    ipv6_interface: IPv6Interface

    # --- Other stdlib ---
    deque_str: deque[str]


BENCH_DATA = BenchData(
    # Primitives
    none_value=None,
    bool_true=True,
    bool_false=False,
    pos_int=42,
    neg_int=-15,
    large_int=10**18,
    pos_float=3.14159,
    neg_float=-2.71828,
    float_precision=0.1 + 0.2,  # 0.30000000000000004
    string="Hello, World!",
    empty_string="",
    unicode_string="Привет, мир! 🌍",
    binary=b"binary_data_bytes",
    empty_bytes=b"",
    # Sequences
    int_list=[1, 2, 3, 4, 5],
    nested_list=[[1, 2], [3, 4], [5, 6]],
    mixed_tuple=(None, True, 42, 3.14, "text", b"data"),
    int_tuple=(1, 2, 3),
    heterogeneous_tuple=(1, "two", 3.0, None),
    bytes_tuple=(b"bytes1", b"bytes2"),
    empty_tuple=(),
    # Sets
    int_set={1, 2, 3, 4, 5},
    str_set={"apple", "banana", "cherry"},
    frozenset_int=frozenset({10, 20, 30}),
    # Mappings
    simple_dict={"name": "Alice", "age": 30, "is_active": True},
    nested_dict={
        "user": {
            "id": 12345,
            "profile": {"first_name": "John", "last_name": "Doe"},
        },
    },
    # Mixed collections
    list_of_sets=[{1, 2}, {3, 4}, {5, 6}],
    tuple_of_lists=([1, 2], [3, 4], [5, 6]),
    # Custom types
    simple_dc=BenchDataclass(1, "test", ["a", "b"], {"x": 1}),
    dc_list=[BenchDataclass(i, f"nm_{i}", [], {}) for i in range(10)],
    nested_dc=NestedBenchDataclass(BenchDataclass(99, "nested", ["root"], {})),
    named_tuple=BenchNamedTuple(1.1, 2.2, "point"),
    # Enums
    str_enum=Status.ACTIVE,
    int_enum=Priority.HIGH,
    flag_enum=Permissions.READ | Permissions.WRITE,
    # UUID
    uuid_v4=uuid.uuid4(),
    uuid_v1=uuid.uuid1(),
    # Date / time
    datetime_utc=datetime.now(ZoneInfo("UTC")),
    datetime_tz=datetime.now(ZoneInfo("Europe/Moscow")),
    date_val=date.today(),  # noqa: DTZ011
    time_val=time(14, 30, 15),
    timedelta_val=timedelta(days=5, hours=3, minutes=30),
    # Numeric
    decimal_val=Decimal("10.123456789"),
    fraction_val=Fraction(1, 3),
    complex_val=complex(2, 5),
    # Paths
    posix_path=Path("/usr/bin/python3"),
    windows_path=Path("C:/Users/Admin/AppData"),
    # IP / network
    ipv4=IPv4Address("192.168.1.1"),
    ipv6=IPv6Address("2001:db8::"),
    ipv4_network=IPv4Network("192.168.0.0/24"),
    ipv4_interface=IPv4Interface("192.168.1.1/24"),
    ipv6_interface=IPv6Interface("2001:db8::1/32"),
    # Other stdlib
    deque_str=deque(["first", "second", "third"]),
)


T = TypeVar("T")


class FakeAdapter(Dumper, Loader):
    @override
    def load(self, data: Any, tp: type[T], /) -> T:
        return cast("T", data)

    @override
    def dump(self, data: Any, tp: Any, /) -> Any:
        return data


def serializer_case(serializer: Serializer, adapter: PairAdapter = UNSET) -> None:
    if adapter is UNSET:
        adapter = FakeAdapter()

    encoded = serializer.dumpb(adapter.dump(BENCH_DATA, BenchData))
    decoded = adapter.load(serializer.loadb(encoded), BenchData)
    assert decoded == BENCH_DATA
