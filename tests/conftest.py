from collections.abc import AsyncIterator
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from iojobs._internal.scheduler import JobScheduler


@pytest.fixture(scope="session")
def now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))


@pytest.fixture
async def scheduler() -> AsyncIterator[JobScheduler]:
    async with JobScheduler() as jobber:
        yield jobber
