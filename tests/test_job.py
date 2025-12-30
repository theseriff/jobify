import asyncio
from unittest.mock import ANY, AsyncMock

import pytest

from jobify import Job
from jobify._internal.common.constants import JobStatus
from jobify._internal.exceptions import DuplicateJobError
from tests.conftest import create_app


async def test_job() -> None:
    app = create_app()

    @app.task(func_name="t")
    def t(num: int) -> int:
        return num + 1

    async with app:
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
    assert job2.id not in job2._pending_jobs
    assert job2._handle
    assert job2._handle.cancelled()


async def test_all_jobs_completed(amock: AsyncMock) -> None:
    app = create_app()
    f = app.task(amock)

    async with app:
        _ = await f.schedule().delay(0)
        _ = await f.schedule().delay(0)
        _ = await f.schedule().delay(0)

        await app.wait_all()

        assert len(app.task._shared_state.pending_jobs) == 0

        _ = await f.schedule().delay(10)
        _ = await f.schedule().delay(10)
        _ = await f.schedule().delay(10)

        with pytest.raises(asyncio.TimeoutError):
            await app.wait_all(timeout=0)

        expected_planned_jobs = 3
        assert (
            len(app.task._shared_state.pending_jobs) == expected_planned_jobs
        )


async def test_duplicate_job_error(amock: AsyncMock) -> None:
    app = create_app()
    f = app.task(amock)
    async with app:
        _ = await f.schedule().delay(0, job_id="test")

        match = "Job with ID 'test' is already scheduled."
        with pytest.raises(DuplicateJobError, match=match):
            _ = await f.schedule().delay(0, job_id="test")


async def test_job_handle_not_set() -> None:
    job = Job[None](
        job_id=ANY,
        exec_at=ANY,
        pending_jobs={},
        job_status=JobStatus.SCHEDULED,
        storage=ANY,
    )
    job._cancel()
