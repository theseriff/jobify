import asyncio
import time
from unittest.mock import Mock

import pytest

from jobify._internal.exceptions import (
    ApplicationStateError,
    JobNotCompletedError,
    JobTimeoutError,
)
from tests.conftest import create_app


async def test_app_runtime_error() -> None:
    app = create_app()

    @app.task
    def f() -> None: ...

    reason = "The Jobify application is not started."
    with pytest.raises(ApplicationStateError, match=reason):
        _ = await f.schedule().delay(0)

    async with app:
        reason = (
            "The Jobify app's already running and configuration is frozen."
        )

        with pytest.raises(ApplicationStateError, match=reason):
            _ = app.task(f, name="test1")

        with pytest.raises(ApplicationStateError, match=reason):
            app.add_middleware(Mock())

        with pytest.raises(ApplicationStateError, match=reason):
            app.add_outer_middleware(Mock())

        with pytest.raises(ApplicationStateError, match=reason):
            app.add_exception_handler(Exception, Mock())


async def test_job_not_completed() -> None:
    app = create_app()

    @app.task(name="f1")
    def f1(num: int) -> int:
        return num + 1

    async with app:
        job = await f1.schedule(1).delay(0)
        match = "Job result is not ready"
        with pytest.raises(JobNotCompletedError, match=match):
            _ = job.result()

        expected_val = 2
        await job.wait()
        assert job.result() == expected_val


async def test_job_timeout() -> None:
    timeout = 0.005
    app = create_app()

    @app.task(timeout=timeout)
    async def f1() -> None:
        await asyncio.sleep(5000)

    @app.task(timeout=timeout)
    def f2() -> None:
        time.sleep(0.01)

    @app.task
    async def f3() -> str:
        return "test"

    async with app:
        job1 = await f1.schedule().delay(0)
        job2 = await f2.schedule().delay(0)
        job3 = await f3.schedule().delay(0)
        await app.wait_all()

        match = (
            "job_id: {id} exceeded timeout of {timeout} seconds. "
            "Job execution was interrupted."
        )
        assert type(job1.exception) is JobTimeoutError
        assert str(job1.exception) == match.format(id=job1.id, timeout=timeout)

        assert type(job2.exception) is JobTimeoutError
        assert str(job2.exception) == match.format(id=job2.id, timeout=timeout)
        assert job3.result() == "test"
