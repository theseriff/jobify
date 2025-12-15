from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest

from jobber import Jobber
from jobber._internal.cron_parser import CronParser, FactoryCron


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


def create_factory_cron() -> FactoryCron:
    def scope() -> Callable[[datetime], datetime]:
        ms = 0

        def now(now: datetime) -> datetime:
            nonlocal ms
            ms += 10
            return now + timedelta(microseconds=ms)

        return now

    cron = Mock(spec=CronParser)
    cron.next_run.side_effect = scope()
    return Mock(return_value=cron)


def create_app() -> Jobber:
    return Jobber(factory_cron=create_factory_cron())
