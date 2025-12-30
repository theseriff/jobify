from collections.abc import Callable
from datetime import datetime, timedelta
from itertools import count
from typing import Any
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest

from jobify import Jobify
from jobify._internal.cron_parser import CronFactory, CronParser


@pytest.fixture(scope="session")
def now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))


@pytest.fixture
def amock() -> AsyncMock:
    async def _stub(*_args: Any, **_kwargs: Any) -> str:  # noqa: ANN401
        raise NotImplementedError

    mock = AsyncMock(spec=_stub, return_value="test")
    mock.__code__ = _stub.__code__
    mock.__defaults__ = _stub.__defaults__
    mock.__kwdefaults__ = _stub.__kwdefaults__
    mock.__annotations__ = _stub.__annotations__
    mock.__module__ = _stub.__module__ or "tests.conftest"
    mock.__name__ = _stub.__name__
    return mock


def cron_next_run(
    init: int = 10,
    step: int = 300,
) -> Callable[[datetime], datetime]:
    cnt = count(init, step=step)

    def next_run(now: datetime) -> datetime:
        return now + timedelta(microseconds=next(cnt))

    return next_run


def create_cron_factory() -> CronFactory:
    cron = Mock(spec=CronParser)
    cron.next_run.side_effect = cron_next_run()
    return Mock(return_value=cron)


def create_app() -> Jobify:
    return Jobify(cron_factory=create_cron_factory(), storage=False)
