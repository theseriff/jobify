# pyright: reportPrivateUsage=false
import asyncio
from datetime import datetime

import pytest

from jobber import Jobber, RunMode
from jobber._internal.cron_parser import CronParser


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
async def test_jobber(  # noqa: PLR0913
    now: datetime,
    cron_parser_cls: type[CronParser],
    *,
    method: str,
    num: int,
    expected: int,
    run_mode: RunMode,
) -> None:
    jobber = Jobber(cron_parser_cls=cron_parser_cls)
    f1_reg = jobber.register(f1, func_name="f1_reg", run_mode=run_mode)
    f2_reg = jobber.register(f2, func_name="f2_reg", run_mode=run_mode)
    async with jobber:
        if method == "at":
            job_sync = await f1_reg.schedule(num).at(now, now=now)
            job_async = await f2_reg.schedule(num).at(now, now=now)
        elif method == "delay":
            job_sync = await f1_reg.schedule(num).delay(0, now=now)
            job_async = await f2_reg.schedule(num).delay(0, now=now)
        elif method == "cron":
            exp = "* * * * *"
            job_sync = await f1_reg.schedule(num).cron(exp, now=now)
            job_async = await f2_reg.schedule(num).cron(exp, now=now)
        else:
            raise NotImplementedError

        _ = await asyncio.gather(job_sync.wait(), job_async.wait())

        if method == "cron":
            await job_sync.cancel()
            await job_async.cancel()

    assert job_sync.result() == expected
    assert job_async.result() == expected
    assert len(jobber.jobber_config.asyncio_tasks) == 0
    assert len(jobber._job_registry) == 0
