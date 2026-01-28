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


async def test_cron_reschedule() -> None:
    app = create_app(0.01)

    @app.task
    def t(name: str) -> str:
        return f"hello, {name}!"

    async with app:
        job = await t.schedule("Biba").cron("* * * * *", job_id="test")

        cur_exec_at = job.exec_at
        await asyncio.wait_for(job.wait(), timeout=1.0)
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
        _ = await asyncio.wait_for(
            asyncio.gather(job.wait(), job.wait()),
            timeout=1.0,
        )

    amock.assert_awaited_once()


async def test_cron_declarative() -> None:
    app = create_app(1)

    @app.task(cron="* * * * * * *")
    async def _() -> str:
        return "ok"

    async with app:
        job = app.task._shared_state.pending_jobs.popitem()[1]
        await asyncio.wait_for(job.wait(), timeout=1.0)

    assert job.result() == "ok"


async def test_cron_shutdown_graceful() -> None:
    app = create_app(1)

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
        cron_parser=cron_parser,
        next_run_at=next_run_at,
        real_now=real_now,
    )

    assert str(GracePolicy(timedelta(days=1)))
    assert handler(policy=MisfirePolicy.ALL) == next_run_at
    assert handler(policy=MisfirePolicy.SKIP) == cron_parser.next_run(
        now=real_now
    )
    assert handler(policy=MisfirePolicy.ONCE) == real_now
    assert (
        handler(policy=MisfirePolicy.GRACE(timedelta(days=8))) == next_run_at
    )
    expected_next_run_at = cron_parser.next_run(
        now=real_now - timedelta(days=6)
    )
    assert (
        handler(policy=MisfirePolicy.GRACE(timedelta(days=6)))
        == expected_next_run_at
    )
    invalid_enum_type: Any = "InvalidEnumType"
    assert handler(policy=invalid_enum_type) is None


async def test_cron_no_reschedule_if_app_stopped() -> None:
    app = create_app(0.01)
    ran_event = asyncio.Event()

    @app.task(cron=Cron("* * * * * * *", max_runs=2))
    async def _() -> str:
        app.configs.app_started = False
        ran_event.set()
        return "done"

    async with app:
        _s = await asyncio.wait_for(ran_event.wait(), timeout=1.0)
        assert not app.task._shared_state.pending_jobs
