from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

import pytest

from iojobs._internal.serializers import (
    AstLiteralSerializer,
    PickleSerializerUnsafe,
)

if TYPE_CHECKING:
    from iojobs._internal.serializers.abc import JobsSerializer

AllowedDataTypes: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | bytes
    | list["AllowedDataTypes"]
    | tuple["AllowedDataTypes"]
    | dict[str, "AllowedDataTypes"]
)


@pytest.mark.parametrize(
    "serializer",
    [
        AstLiteralSerializer(),
        PickleSerializerUnsafe(),
    ],
)
@pytest.mark.parametrize(
    "data",
    [
        None,
        True,
        False,
        123,
        123.45,
        "hello",
        b"world",
        [1, "a", None],
        (1, "a", None),
        {"a": 1, "b": None},
        {1, "a", None},
    ],
)
def test_serialization_all(
    serializer: JobsSerializer,
    data: AllowedDataTypes,
) -> None:
    """Tests that all serializers can serialize and deserialize basic Python types."""  # noqa: E501
    # The AstLiteralSerializer has a bug and will fail this test for strings.
    # It should use repr(value) instead of str(value) in its dumpb method.
    serialized = serializer.dumpb(data)
    deserialized = serializer.loadb(serialized)
    assert deserialized == data
