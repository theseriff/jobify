from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict
from unittest.mock import AsyncMock

from jobify import Jobify


async def test_lifespan_with_state() -> None:
    client = AsyncMock()

    class State(TypedDict):
        client: AsyncMock

    @asynccontextmanager
    async def lifespan(_: Jobify) -> AsyncIterator[State]:
        async with client:
            yield {"client": client}

    app = Jobify(lifespan=lifespan, storage=False)

    assert not hasattr(app.state, "client")

    await app.startup()

    assert hasattr(app.state, "client")

    client.__aenter__.assert_awaited_once()
    client.__aexit__.assert_not_awaited()

    await app.shutdown()

    client.__aexit__.assert_awaited_once()
