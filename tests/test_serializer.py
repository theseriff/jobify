import pytest

from iojobs.serializers import (
    JobsSerializer,
    JSONSerializer,
    SerializableTypes,
    UnsafePickleSerializer,
)


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
