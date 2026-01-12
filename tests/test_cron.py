import asyncio
import functools
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

from jobify import Cron, GracePolicy, MisfirePolicy
from jobify._internal.scheduler.misfire_policy import handle_misfire_policy
from jobify.crontab import create_crontab
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
    app = create_app()

    @app.task
    def t(name: str) -> str:
        return f"hello, {name}!"

    async with app:
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

    app = create_app()
    match = "max_cron_failures must be >= 1. Use 1 for 'stop on first error'."
    with pytest.raises(ValueError, match=match):
        _ = app.task(amock, cron=Cron("", max_failures=-1))

    max_failures = 1
    f = app.task(amock)
    async with app:
        expression = "* * * * * * *"  # every seconds
        job = await f.schedule().cron(
            Cron(expression, max_failures=max_failures),
            job_id="test",
        )
        await job.wait()
        await job.wait()

    amock.assert_awaited_once()


async def test_cron_declarative() -> None:
    app = create_app()

    @app.task(cron="* * * * * * *")
    async def _() -> str:
        return "ok"

    async with app:
        job = app.task._shared_state.pending_jobs.popitem()[1]
        await job.wait()

    assert job.result() == "ok"


async def test_cron_shutdown_graceful() -> None:
    app = create_app()

    @app.task(cron="* * * * * * *")
    async def _() -> None:
        await asyncio.sleep(3)

    async with app:
        await asyncio.sleep(0.005)
        task = app.task._shared_state.pending_tasks.pop()
        _is_cancelled = task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(app.task._shared_state.pending_jobs) == 0


def test_misfire_policy() -> None:
    real_now = datetime.now(timezone.utc)
    cron_parser = create_crontab("* * * * *")
    next_run_at = cron_parser.next_run(now=real_now - timedelta(days=7))
    handler = functools.partial(
        handle_misfire_policy,
        cron_parser,
        next_run_at,
        real_now,
    )

    assert str(GracePolicy(timedelta(days=1)))
    assert handler(MisfirePolicy.ALL) == next_run_at
    assert handler(MisfirePolicy.SKIP) == cron_parser.next_run(now=real_now)
    assert handler(MisfirePolicy.ONCE) == real_now
    assert handler(MisfirePolicy.GRACE(timedelta(days=8))) == next_run_at
    expected_next_run_at = cron_parser.next_run(
        now=real_now - timedelta(days=6)
    )
    assert (
        handler(MisfirePolicy.GRACE(timedelta(days=6))) == expected_next_run_at
    )
    invalid_enum_type: Any = "InvalidEnumType"
    assert handler(invalid_enum_type) is None
