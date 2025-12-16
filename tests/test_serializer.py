import dataclasses
from dataclasses import dataclass
from typing import Any, NamedTuple

import pytest

from jobber.serializers import (
    JobsSerializer,
    JSONSerializer,
    SerializableTypes,
    UnsafePickleSerializer,
)


class SimpleData(NamedTuple):
    id: int
    name: str
    value: bytes


class NestedData(NamedTuple):
    key: str
    data: SimpleData


@dataclass(slots=True, kw_only=True, frozen=True, eq=False)
class PointDC:
    x: int
    y: int
    label: str | None = None


@dataclass(slots=True, kw_only=True, frozen=True, eq=False)
class ComplexDC:
    id: int
    raw_data: bytes
    point: PointDC


@pytest.mark.parametrize(
    "serializer",
    [
        pytest.param(UnsafePickleSerializer()),
        pytest.param(JSONSerializer()),
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
    ],
)
def test_serialization_all(
    serializer: JobsSerializer,
    data: SerializableTypes,
) -> None:
    """Tests that all serializers can [de]serialize basic Python types."""
    serialized = serializer.dumpb(data)
    deserialized = serializer.loadb(serialized)
    assert deserialized == data


@pytest.mark.parametrize(
    "serializer",
    [
        pytest.param(UnsafePickleSerializer()),
        pytest.param(JSONSerializer()),
    ],
)
@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            PointDC(x=10, y=20, label="origin"),
            id="SimpleDataclass",
        ),
        pytest.param(
            ComplexDC(id=99, raw_data=b"binary", point=PointDC(x=1, y=2)),
            id="NestedDataclassWithBytes",
        ),
    ],
)
def test_serialization_dataclass(
    serializer: JobsSerializer,
    data: Any,  # noqa: ANN401
) -> None:
    serialized = serializer.dumpb(data)
    deserialized: Any = serializer.loadb(serialized)

    data_params = data.__class__.__dataclass_params__
    deser_params = deserialized.__class__.__dataclass_params__

    assert dataclasses.asdict(data) == dataclasses.asdict(deserialized)
    assert data_params.slots == deser_params.slots is True
    assert data_params.frozen == deser_params.frozen is True
    assert data_params.kw_only == deser_params.kw_only is True
    assert data_params.eq == deser_params.eq is False
