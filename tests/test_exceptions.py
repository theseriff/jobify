from datetime import datetime
from typing import TypedDict

import pytest

from iojobs import JobScheduler
from iojobs._internal.exceptions import (
    JobNotCompletedError,
    JobNotInitializedError,
    NegativeDelayError,
)


class CommonKwargs(TypedDict):
    now: datetime
    to_thread: bool
    to_process: bool


scheduler = JobScheduler()


@scheduler.register(func_name="f1")
def f1(num: int) -> int:
    return num + 1


async def test_job_not_completed() -> None:
    job = await f1.schedule(1).delay(0)
    with pytest.raises(JobNotCompletedError, match="Job result is not ready"):
        _ = job.result()

    expected_val = 2
    await job.wait()
    assert job.result() == expected_val


async def test_negative_delay() -> None:
    with pytest.raises(NegativeDelayError, match="Negative delay_seconds"):
        _ = await f1.schedule(2).delay(-1)


async def test_job_not_initialized() -> None:
    with pytest.raises(JobNotInitializedError, match="Job is not initialized"):
        _ = f1.schedule(2).job
