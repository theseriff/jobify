from collections.abc import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from iojobs._internal.scheduler import JobScheduler


@pytest.fixture(scope="session")
def now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))


@pytest.fixture
def scheduler() -> Iterable[JobScheduler]:
    scheduler = JobScheduler()
    scheduler.startup()
    yield scheduler
    scheduler.shutdown()
