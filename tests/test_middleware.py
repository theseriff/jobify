# ruff: noqa: ANN401
# pyright: reportPrivateUsage=false
import inspect
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock

import pytest

from jobber import Jobber, JobContext, JobStatus
from jobber.exceptions import JobSkippedError
from jobber.middleware import BaseMiddleware, CallNext


class MyMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.skip: bool = False

    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        if self.skip:
            return None
        self.skip = True
        return await call_next(context)


async def test_middleware() -> None:
    amock = AsyncMock(return_value=1)
    amock.__signature__ = inspect.Signature()

    jobber = Jobber(middleware=[MyMiddleware()])
    f = jobber.register(amock)

    async with jobber:
        job = await f.schedule(2).delay(0)
        await job.wait()
        assert job.status is JobStatus.SUCCESS
        amock.assert_awaited_once_with(2)
        amock.reset_mock()

        job = await f.schedule(2).delay(0)
        await job.wait()
        assert job.status is JobStatus.SKIPPED
        with pytest.raises(
            JobSkippedError,
            match=r"Job was not executed\. A middleware short-circuited",
        ):
            _ = job.result()
        amock.assert_not_awaited()


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
