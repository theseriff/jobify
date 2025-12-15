import asyncio
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

from jobber import Cron
from jobber.crontab import create_crontab
from tests.conftest import create_app


def test_cronparser() -> None:
    crontab = create_crontab("@daily")
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    next_run = crontab.next_run(now=now)
    expected_run = (now + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    assert next_run == expected_run


async def test_cron_reschedule(now: datetime) -> None:
    jobber = create_app()

    @jobber.task
    def t(name: str) -> str:
        return f"hello, {name}!"

    async with jobber:
        job = await t.schedule("Biba").cron(
            "* * * * *",
            job_id="test",
            now=now,
        )

        cur_exec_at = job.exec_at
        await job.wait()
        next_exec_at = job.exec_at

        assert job.result() == "hello, Biba!"
        assert cur_exec_at != next_exec_at


async def test_max_cron_failures(amock: mock.AsyncMock) -> None:
    amock.side_effect = ValueError

    jobber = create_app()
    match = "max_cron_failures must be >= 1. Use 1 for 'stop on first error'."
    with pytest.raises(ValueError, match=match):
        _ = jobber.task(amock, cron=Cron("", max_failures=-1))

    max_failures = 1
    f = jobber.task(amock)
    async with jobber:
        expression = "* * * * * * *"  # every seconds
        job = await f.schedule().cron(
            Cron(expression, max_failures=max_failures),
            job_id="test",
        )
        await job.wait()
        await job.wait()

    amock.assert_awaited_once()
    assert not job.should_reschedule(max_failures)


async def test_cron_declarative() -> None:
    jobber = create_app()

    @jobber.task(cron="* * * * * * *")
    async def _() -> str:
        return "ok"

    async with jobber:
        job = jobber.jobber_config._jobs_registry.popitem()[1]
        await job.wait()

    assert job.result() == "ok"


async def test_cron_shutdown_graceful() -> None:
    jobber = create_app()

    @jobber.task(cron="* * * * * * *")
    async def _() -> None:
        await asyncio.sleep(3)

    async with jobber:
        await asyncio.sleep(0.001)
        task = jobber.jobber_config._tasks_registry.pop()
        _is_cancelled = task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(jobber.jobber_config._jobs_registry) == 0
