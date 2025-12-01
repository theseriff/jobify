from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from jobber._internal.cron_parser import CronParser


@pytest.fixture(scope="session")
def now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))


def now_(now: datetime) -> datetime:
    return now + timedelta(microseconds=300)


@pytest.fixture(scope="session")
def cron_parser_cls() -> CronParser:
    cron = Mock(spec=CronParser)
    cron.next_run.side_effect = now_
    cron.get_expression.return_value = "* * * * * *"
    return Mock(return_value=cron, spec=type[CronParser])
