import inspect
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest

from jobber import Jobber
from jobber._internal.cron_parser import CronParser, FactoryCron


def now_(now: datetime) -> datetime:
    return now + timedelta(microseconds=300)


@pytest.fixture(scope="session")
def now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))


@pytest.fixture
def amock() -> AsyncMock:
    mock = AsyncMock(return_value="test")
    mock.__signature__ = inspect.Signature()
    return mock


def create_factory_cron() -> FactoryCron:
    cron = Mock(spec=CronParser)
    cron.next_run.side_effect = now_
    cron.get_expression.return_value = "* * * * * *"

    def factory(_: str) -> CronParser:
        return cron

    return factory


@pytest.fixture(scope="session")
def cron_parser() -> FactoryCron:
    return create_factory_cron()


def create_app() -> Jobber:
    return Jobber(factory_cron=create_factory_cron())
