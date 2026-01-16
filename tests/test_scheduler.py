import asyncio
from datetime import datetime

import pytest

from jobify import Cron, Jobify, JobRouter, RunMode
from jobify._internal.router.base import Router
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
