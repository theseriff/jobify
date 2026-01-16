import asyncio
from datetime import datetime, timedelta, timezone
from typing import Literal, cast
from unittest.mock import AsyncMock

import pytest

from jobify import Cron, Job, Jobify, JobRouter, RunMode
from jobify._internal.message import CronArguments, Message
from jobify._internal.router.base import Router
from jobify.storage import SQLiteStorage
from tests.conftest import create_app


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
            job_sync = await f1_reg.schedule(num).cron(
                cron, job_id="test1", now=now
            )
            job_async = await f2_reg.schedule(num).cron(
                cron, job_id="test2", now=now
            )
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
            _ = await builder.cron("5 0 * 8 *", job_id=job_id)
            j = await builder.cron(
                Cron("5 0 * 7 *"),
                job_id="job_test",
                replace=True,
            )
            job_cron: Job[None] | None = app.find_job(job_id)
            assert job_cron is not None
            assert job_cron.cron_expression == "5 0 * 7 *"
        elif method == "delay":
            _ = await builder.delay(20, job_id=job_id)
            j = await builder.delay(60, job_id=job_id, replace=True)
        else:
            now = datetime.now(tz=timezone.utc)
            _ = await builder.at(now + timedelta(1), job_id=job_id)
            j = await builder.at(
                now + timedelta(2),
                job_id=job_id,
                replace=True,
            )

        job: Job[None] | None = app.find_job(job_id)
        assert len(app.task._shared_state.pending_jobs) == 1
        assert job is not None
        assert job is j
        assert job.exec_at == j.exec_at

        if storage is not False:  # pragma: no cover
            schedules = await storage.get_schedules()
            scheduled_job = schedules[0]

            assert len(schedules) == 1
            assert scheduled_job.next_run_at == job.exec_at
            if job.cron_expression:
                trigger = cast(
                    "CronArguments",
                    app.configs.loader.load(
                        app.configs.serializer.loadb(scheduled_job.message),
                        Message,
                    ).trigger,
                )
                assert trigger.offset == job._offset
