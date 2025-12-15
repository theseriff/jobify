import asyncio
from unittest.mock import AsyncMock

import pytest

from jobber import Jobber
from jobber._internal.common.constants import JobStatus
from jobber._internal.exceptions import DuplicateJobError


async def test_job() -> None:
    jobber = Jobber()

    @jobber.task(name="t")
    def t(num: int) -> int:
        return num + 1

    async with jobber:
        job1 = await t.schedule(1).delay(0)
        job2 = await t.schedule(1).delay(1)
        await job2.cancel()
        await job1.wait()

    expected_return = 2
    assert job1.result() == expected_return
    assert str(job1).startswith(f"Job(instance_id={id(job1)}")
    assert str(job2).startswith(f"Job(instance_id={id(job2)}")
    assert job2.is_done()
    assert job2.status is JobStatus.CANCELLED
    assert job2.id not in job2._jobs_registry
    assert job2._timer_handler.cancelled()


async def test_all_jobs_completed(amock: AsyncMock) -> None:
    app = Jobber()
    f = app.task(amock)

    async with app:
        _ = await f.schedule().delay(0)
        _ = await f.schedule().delay(0)
        _ = await f.schedule().delay(0)

        await app.wait_all()

        assert len(app.jobber_config._jobs_registry) == 0

        _ = await f.schedule().delay(10)
        _ = await f.schedule().delay(10)
        _ = await f.schedule().delay(10)

        with pytest.raises(asyncio.TimeoutError):
            await app.wait_all(timeout=0)

        expected_planned_jobs = 3
        assert len(app.jobber_config._jobs_registry) == expected_planned_jobs


async def test_duplicate_job_error(amock: AsyncMock) -> None:
    app = Jobber()
    f = app.task(amock)
    async with app:
        _ = await f.schedule().delay(0, job_id="test")

        match = "Job with ID 'test' is already scheduled."
        with pytest.raises(DuplicateJobError, match=match):
            _ = await f.schedule().delay(0, job_id="test")
