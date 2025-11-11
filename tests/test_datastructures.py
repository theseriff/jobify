from unittest.mock import AsyncMock

import pytest

from iojobs._internal.datastructures import EmptyPlaceholder, State


def test_empty_placeholder() -> None:
    empty = EmptyPlaceholder()
    assert str(empty) == "EMPTY"
    assert hash(empty) == hash("EMPTY")
    assert bool(empty) is False
    assert empty == EmptyPlaceholder()


async def test_state() -> None:
    client = AsyncMock()
    state = State(state={"client": client})
    state.new_client = AsyncMock()
    await state.client.post(url="https://")
    assert hasattr(state, "_state")
    assert hasattr(state, "client")
    assert hasattr(state, "new_client")
    state.client.post.assert_awaited_once_with(url="https://")
    with pytest.raises(AttributeError):
        _ = state.non_exists_key

    del state.new_client
    assert not hasattr(state, "new_client")
