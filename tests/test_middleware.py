# ruff: noqa: ANN401
# pyright: reportPrivateUsage=false
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock

import pytest

from jobber import Jobber, JobContext, JobStatus
from jobber.exceptions import JobSkippedError
from jobber.middleware import BaseMiddleware, CallNext


class MyMiddleware(BaseMiddleware):
    def __init__(self, *, skip: bool = False) -> None:
        self.skip: bool = skip

    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        if self.skip is True:
            return None
        return await call_next(context)


@pytest.mark.parametrize(
    ("skip", "status"),
    [
        (True, JobStatus.SKIPPED),
        (False, JobStatus.SUCCESS),
    ],
)
async def test_middleware(*, skip: bool, status: JobStatus) -> None:
    jobber = Jobber(middleware=[MyMiddleware(skip=skip)])

    @jobber.register
    async def t1(num: int) -> int:
        return num + 1

    async with jobber:
        job = await t1.schedule(2).delay(0)
        await job.wait()

        assert job.status is status
        if status is JobStatus.SKIPPED:
            match = "Job was not executed. A middleware short-circuited"
            with pytest.raises(JobSkippedError, match=match):
                _ = job.result()


async def test_exception_middleware() -> None:
    jobber = Jobber()

    @jobber.register
    async def f1() -> None:
        raise ValueError

    @jobber.register
    async def f2() -> None:
        raise TimeoutError

    sync_handler = Mock()
    async_handler = AsyncMock()
    jobber.exception_handler.use(ValueError, sync_handler)
    jobber.exception_handler.use(TimeoutError, async_handler)

    async with jobber:
        job1 = await f1.schedule().delay(0)
        job2 = await f2.schedule().delay(0)
        await job1.wait()
        await job2.wait()

        sync_handler.assert_called_once_with(ANY, job1._exception)
        async_handler.assert_awaited_once_with(ANY, job2._exception)
