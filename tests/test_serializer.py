import dataclasses
from dataclasses import dataclass, is_dataclass
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
        pytest.param(JSONSerializer(type_registry), id="json"),
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
        *named_tuple_structures,
        *dataclass_structures,
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


def _ensure_has_param(param: str, params1: Any, params2: Any) -> bool:  # noqa: ANN401
    return getattr(params1, param, True) is getattr(params2, param, True)


@pytest.mark.parametrize("serializer", [JSONSerializer({})])
@pytest.mark.parametrize(
    "data",
    [*dataclass_structures, *named_tuple_structures],
)
def test_serialization_fallback_create_structure(
    serializer: JSONSerializer,
    data: SerializableTypes,
) -> None:
    serialized = serializer.dumpb(data)
    deserialized: Any = serializer.loadb(serialized)

    assert len(serializer.decoder_hook.registry) > 0
    if is_dataclass(data):
        assert dataclasses.asdict(data) == dataclasses.asdict(deserialized)
        d_cls: Any = data.__class__
        data_params = d_cls.__dataclass_params__
        deser_params = deserialized.__class__.__dataclass_params__
        assert data_params.frozen is deser_params.frozen
        assert _ensure_has_param("kw_only", data_params, deser_params)
        assert _ensure_has_param("slots", data_params, deser_params)
    else:
        assert data == deserialized
