from collections.abc import AsyncIterator
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jobber._internal.jobber import Jobber


@pytest.fixture(scope="session")
def now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))


@pytest.fixture
async def jobber() -> AsyncIterator[Jobber]:
    async with Jobber() as jobber:
        yield jobber
