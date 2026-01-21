import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Literal, cast
from unittest.mock import AsyncMock

import pytest

from jobify import Cron, Job, Jobify, JobRouter, RunMode
from jobify._internal.message import CronArguments, Message
from jobify._internal.router.base import Router
from jobify.storage import SQLiteStorage
from tests.conftest import create_app

if TYPE_CHECKING:
    from jobify._internal.scheduler.job import CronContext


@pytest.fixture(params=[create_app, JobRouter])
def node(request: pytest.FixtureRequest) -> Router:
    router: Router = request.param()
    return router


def f1(num: int) -> int:
    return num + 1


async def f2(num: int) -> int:
    return num + 1


@pytest.mark.parametrize(
    "run_mode",
    [
        pytest.param(RunMode.MAIN, id="main"),
        pytest.param(RunMode.THREAD, id="thread"),
        pytest.param(RunMode.PROCESS, id="process"),
    ],
)
@pytest.mark.parametrize(
    ("method", "num", "expected"),
    [
        pytest.param("at", 1, 2),
        pytest.param("cron", 3, 4),
        pytest.param("delay", 2, 3),
    ],
)
async def test_jobify(  # noqa: PLR0913
    now: datetime,
    node: Router,
    *,
    method: str,
    num: int,
    expected: int,
    run_mode: RunMode,
) -> None:
    f1_reg = node.task(f1, name="f1_reg", run_mode=run_mode)
    f2_reg = node.task(f2, name="f2_reg", run_mode=run_mode)
    if type(node) is Jobify:
        app = node
    else:
        app = create_app()
        app.include_router(node)
    async with app:
        if method == "at":
            job_sync = await f1_reg.schedule(num).at(now)
            job_async = await f2_reg.schedule(num).at(now)
        elif method == "delay":
            job_sync = await f1_reg.schedule(num).delay(0, now=now)
            job_async = await f2_reg.schedule(num).delay(0, now=now)
        elif method == "cron":
            cron = Cron("* * * * *", max_runs=1)
            job_sync = await f1_reg.schedule(num).cron(cron, job_id="test1")
            job_async = await f2_reg.schedule(num).cron(cron, job_id="test2")
        else:
            raise NotImplementedError

        _ = await asyncio.gather(job_sync.wait(), job_async.wait())

    assert job_sync.result() == expected
    assert job_async.result() == expected
    assert app.task._shared_state.pending_jobs == {}
    assert app.task._shared_state.pending_tasks == set()


@pytest.mark.parametrize("storage", [False, SQLiteStorage(":memory:")])
@pytest.mark.parametrize("method", ["at", "cron", "delay"])
async def test_schedule_replace(
    method: str,
    amock: AsyncMock,
    *,
    storage: Literal[False] | SQLiteStorage,
) -> None:
    job_id = "job_test"
    app = Jobify(storage=storage)
    f = app.task(amock)

    async with app:
        builder = f.schedule()
        if method == "cron":
            first_job = await builder.cron("5 0 * 8 *", job_id=job_id)
            first_handle = first_job._handle
            second_job = await builder.cron(
                Cron("5 0 * 7 *"),
                job_id="job_test",
                replace=True,
            )
            cron_job: Job[None] | None = app.find_job(job_id)
            assert cron_job is not None
            assert cron_job.cron_expression == "5 0 * 7 *"
        elif method == "delay":
            first_job = await builder.delay(20, job_id=job_id)
            first_handle = first_job._handle
            second_job = await builder.delay(60, job_id=job_id, replace=True)
        else:
            now = datetime.now(tz=timezone.utc)
            first_job = await builder.at(now + timedelta(1), job_id=job_id)
            first_handle = first_job._handle
            second_job = await builder.at(
                now + timedelta(2),
                job_id=job_id,
                replace=True,
            )

        assert first_handle is not None
        assert first_handle.cancelled()
        assert first_handle is not second_job._handle
        assert first_job is second_job
        assert first_job.exec_at == second_job.exec_at

        job: Job[None] | None = app.find_job(job_id)
        assert len(app.task._shared_state.pending_jobs) == 1
        assert job is not None
        assert job is second_job
        assert job.exec_at == second_job.exec_at

        if storage is not False:  # pragma: no cover
            schedules = await storage.get_schedules()
            scheduled_job = schedules[0]

            assert len(schedules) == 1
            assert scheduled_job.next_run_at == job.exec_at
            if job._cron_context:
                trigger = cast(
                    "CronArguments",
                    app.configs.loader.load(
                        app.configs.serializer.loadb(scheduled_job.message),
                        Message,
                    ).trigger,
                )
                assert trigger.offset == job._cron_context.offset


async def test_schedule_with_none_handle(amock: AsyncMock) -> None:
    app = create_app()
    f = app.task(amock)
    async with app:
        job = await f.schedule().delay(5, job_id="111")
        job._handle = None
        job = await f.schedule().delay(5, job_id="111", replace=True)


async def test_update_exists_job(amock: AsyncMock) -> None:
    app = create_app()
    f = app.task(amock)
    start_date = datetime.now(timezone.utc) + timedelta(1)
    async with app:
        job1 = await f.schedule().cron(
            Cron("* * * * *", start_date=start_date),
            job_id="111",
            replace=True,
        )
        ctx1 = cast("CronContext[None]", job1._cron_context)
        offset1 = ctx1.offset
        start_date1 = ctx1.cron.start_date

        job2 = await f.schedule().cron(
            Cron("* * * * *", start_date=start_date),
            job_id="111",
            replace=True,
        )
        ctx2 = cast("CronContext[None]", job2._cron_context)
        offset2 = ctx2.offset
        start_date2 = ctx2.cron.start_date

        job3 = await f.schedule().cron(
            Cron("* * * * *", start_date=None),
            job_id="111",
            replace=True,
        )
        ctx3 = cast("CronContext[None]", job3._cron_context)
        offset3 = ctx3.offset
        start_date3 = ctx3.cron.start_date

        job4 = await f.schedule().cron(
            Cron("* * * * *", start_date=start_date + timedelta(1)),
            job_id="111",
            replace=True,
        )
        ctx4 = cast("CronContext[None]", job4._cron_context)
        offset4 = ctx4.offset
        start_date4 = ctx4.cron.start_date

    assert offset1 == offset2
    assert start_date1 == start_date2
    assert offset3 == offset2
    assert start_date3 is None
    assert offset4 == start_date4 == start_date + timedelta(1)
