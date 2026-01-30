import asyncio
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, call

from typing_extensions import override

from jobify import JobContext, JobStatus, OuterContext
from jobify.middleware import (
    BaseMiddleware,
    BaseOuterMiddleware,
    CallNext,
    CallNextOuter,
)
from tests.conftest import create_app


class MyMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.skip: bool = False

    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        if self.skip:
            return None
        self.skip = True
        return await call_next(context)


async def test_common_case(amock: mock.AsyncMock) -> None:
    app = create_app()
    app.add_middleware(MyMiddleware())
    f = app.task(amock)

    async with app:
        job = await f.schedule(2).delay(0)
        await job.wait()
        assert job.status is JobStatus.SUCCESS
        amock.assert_awaited_once_with(2)
        amock.reset_mock()

        job = await f.schedule(2).delay(0)
        await job.wait()
        amock.assert_not_awaited()


async def test_exception() -> None:
    app = create_app()

    @app.task
    async def f1() -> None:
        raise ValueError

    @app.task
    async def f2() -> None:
        raise ZeroDivisionError

    sync_handler = mock.Mock()
    async_handler = mock.AsyncMock()
    app.add_exception_handler(ValueError, sync_handler)
    app.add_exception_handler(ZeroDivisionError, async_handler)

    async with app:
        job1 = await f1.schedule().delay(0)
        job2 = await f2.schedule().delay(0)
        await job1.wait()
        await job2.wait()

    sync_handler.assert_called_once_with(job1.exception, mock.ANY)
    async_handler.assert_awaited_once_with(job2.exception, mock.ANY)


@mock.patch("asyncio.sleep", spec=asyncio.sleep)
async def test_retry(
    sleep_mock: mock.AsyncMock,
    *,
    amock: mock.AsyncMock,
) -> None:
    amock.side_effect = ValueError

    retry = 3
    app = create_app()
    f = app.task(amock, retry=retry)
    async with app:
        job = await f.schedule().delay(0)
        await job.wait()

    amock.assert_has_awaits([call()] * (retry + 1))
    sleep_mock.assert_has_awaits(
        mock.call(min(2**attempt, 60)) for attempt in range(retry)
    )


async def test_outer_middlewares(amock: AsyncMock) -> None:
    handle: asyncio.Handle | None = None

    class MyOuterMiddleware(BaseOuterMiddleware):
        @override
        async def __call__(
            self,
            call_next: CallNextOuter,
            context: OuterContext,
        ) -> Any:
            nonlocal handle
            handle = await call_next(context)

    app = create_app()
    f = app.task(amock)
    app.add_outer_middleware(MyOuterMiddleware())
    async with app:
        job = await f.schedule().delay(0.01)
        assert job._handle is handle is not None
