# pyright: reportPrivateUsage=false
import asyncio
from datetime import datetime
from unittest import mock

import pytest

from jobber import ExecutionMode, Jobber
from jobber._internal.common.cron_parser import CronParser


def f1(num: int) -> int:
    return num + 1


async def f2(num: int) -> int:
    return num + 1


@pytest.mark.parametrize(
    "exec_mode",
    [
        pytest.param(ExecutionMode.MAIN, id="main"),
        pytest.param(ExecutionMode.THREAD, id="thread"),
        pytest.param(ExecutionMode.PROCESS, id="process"),
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
@pytest.mark.filterwarnings("ignore:.*(to_thread|to_process).*:RuntimeWarning")
async def test_jobber(  # noqa: PLR0913
    jobber: Jobber,
    now: datetime,
    *,
    method: str,
    num: int,
    expected: int,
    exec_mode: ExecutionMode,
) -> None:
    f1_reg = jobber.register(f1, job_name="f1_reg", exec_mode=exec_mode)
    f2_reg = jobber.register(f2, job_name="f2_reg", exec_mode=exec_mode)
    if method == "at":
        job_sync = await f1_reg.schedule(num).at(now, now=now)
        job_async = await f2_reg.schedule(num).at(now, now=now)
    elif method == "delay":
        job_sync = await f1_reg.schedule(num).delay(0, now=now)
        job_async = await f2_reg.schedule(num).delay(0, now=now)
    elif method == "cron":
        with mock.patch.object(CronParser, "next_run", return_value=now) as m:
            job_sync = await f1_reg.schedule(num).cron("* * * * *", now=now)
            job_async = await f2_reg.schedule(num).cron("* * * * *", now=now)
        m.assert_has_calls(calls=[mock.call(now=now), mock.call(now=now)])
    else:
        raise NotImplementedError

    _ = await asyncio.gather(job_sync.wait(), job_async.wait())
    if method == "cron":
        await job_sync.cancel()
        await job_async.cancel()

    assert job_sync.result() == expected
    assert job_async.result() == expected
    assert jobber._app_ctx.asyncio_tasks == set()
    assert jobber._job_registry == {}
