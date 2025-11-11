from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict
from unittest.mock import AsyncMock

from iojobs._internal.scheduler import JobScheduler


async def test_lifespan_with_state() -> None:
    client = AsyncMock()

    class State(TypedDict):
        client: AsyncMock

    @asynccontextmanager
    async def lifespan(_: JobScheduler) -> AsyncIterator[State]:
        async with client:
            yield {"client": client}

    jobber = JobScheduler(lifespan=lifespan)

    assert not hasattr(jobber.state, "client")

    await jobber.startup()

    assert hasattr(jobber.state, "client")

    client.__aenter__.assert_awaited_once()
    client.__aexit__.assert_not_awaited()

    await jobber.shutdown()

    client.__aexit__.assert_awaited_once()
