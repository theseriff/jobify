import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch, sentinel

import pytest
from typing_extensions import override

from jobify import JobContext, JobStatus, OuterContext
from jobify._internal.common.types import UNSET
from jobify._internal.configuration import SmartRetry
from jobify.middleware import (
    BaseMiddleware,
    BaseOuterMiddleware,
    CallNext,
    CallNextOuter,
    Item,
    JobifyQueue,
    QueueMiddleware,
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


class GateQueue:
    def __init__(self, queue: JobifyQueue) -> None:
        self._queue = queue
        self._ready = asyncio.Event()

    def release(self) -> None:
        self._ready.set()

    async def get(self) -> Item:
        await self._ready.wait()
        return await self._queue.get()

    async def put(self, item: Item) -> None:
        await self._queue.put(item)

    def task_done(self) -> None:
        self._queue.task_done()


async def test_common_case(amock: AsyncMock) -> None:
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

    result = sentinel.RESULT
    mock = Mock()

    def sync_handler(exc: Exception, context: JobContext) -> Any:  # noqa: ANN401
        if context.job.id in ("job3", "job4"):
            return result
        mock(exc)
        raise exc

    async def async_handler(exc: Exception, context: JobContext) -> Any:  # noqa: ANN401
        if context.job.id in ("job3", "job4"):
            return result
        mock(exc)
        raise exc

    app.add_exception_handler(ValueError, sync_handler)
    app.add_exception_handler(ZeroDivisionError, async_handler)

    async with app:
        job1 = await f1.schedule().delay(0)
        job2 = await f2.schedule().delay(0)
        job3 = await f1.schedule().delay(0, job_id="job3")
        job4 = await f2.schedule().delay(0, job_id="job4")

        await job1.wait()
        await job2.wait()
        await job3.wait()
        await job4.wait()

        mock.assert_has_calls([call(job1.exception), call(job2.exception)])
        assert job3.result() is result
        assert job4.result() is result


@patch("asyncio.sleep", spec=asyncio.sleep)
async def test_retry(sleep_mock: AsyncMock, *, amock: AsyncMock) -> None:
    amock.side_effect = ValueError

    retry = 3
    app = create_app()
    f = app.task(amock, retry=retry)
    async with app:
        job = await f.schedule().delay(0)
        await job.wait()

    assert isinstance(f.options.get("retry"), SmartRetry)

    amock.assert_has_awaits([call()] * (retry + 1))
    assert sleep_mock.await_count == retry


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


@pytest.mark.parametrize(
    "queue",
    [
        pytest.param(UNSET, id="Default Queue"),
        pytest.param(asyncio.Queue(), id="Simple Queue"),
        pytest.param(asyncio.LifoQueue(), id="Lifo Queue"),
        pytest.param(asyncio.PriorityQueue(), id="Priority Queue"),
    ],
)
async def test_queue_middleware(queue: JobifyQueue, amock: AsyncMock) -> None:
    amock.side_effect = [1, ValueError()]
    app = create_app()
    app.add_middleware(QueueMiddleware(queue, workers=10))
    f = app.task(amock)

    async with app:
        job1 = await f.push()
        await job1.wait()
        job2 = await f.push()
        await job2.wait()

    amock.assert_has_awaits([call(), call()])
    assert job1.result() == 1
    assert isinstance(job2.exception, ValueError)


async def test_queue_middleware_simple_queue_keeps_fifo_order() -> None:
    queue = GateQueue(asyncio.Queue())
    app = create_app()
    app.add_middleware(QueueMiddleware(queue, workers=1))
    executed: list[str] = []

    @app.task(metadata={"priority": 100})
    async def run_job(label: str) -> str:
        executed.append(label)
        return label

    async with app:
        first = await run_job.push("first")
        second = await run_job.push("second")
        queue.release()
        await asyncio.gather(first.wait(), second.wait())

    assert executed == ["first", "second"]
    assert first.result() == "first"
    assert second.result() == "second"


async def test_queue_middleware_priority_queue_prefers_higher_priority() -> None:
    queue = GateQueue(asyncio.PriorityQueue())
    app = create_app()
    app.add_middleware(QueueMiddleware(queue, workers=1))
    executed: list[str] = []

    @app.task(metadata={"priority": 1})
    async def low_priority() -> str:
        executed.append("low")
        return "low"

    @app.task(metadata={"priority": 10})
    async def high_priority() -> str:
        executed.append("high")
        return "high"

    async with app:
        low = await low_priority.push()
        high = await high_priority.push()
        queue.release()
        await asyncio.gather(low.wait(), high.wait())

    assert executed == ["high", "low"]
    assert high.result() == "high"
    assert low.result() == "low"


@pytest.mark.parametrize(
    "queue",
    [
        pytest.param(asyncio.Queue(), id="Simple Queue"),
        pytest.param(asyncio.PriorityQueue(), id="Priority Queue"),
    ],
)
async def test_queue_middleware_shutdown_completes_queue(
    queue: asyncio.Queue[Item],
) -> None:
    app = create_app()
    app.add_middleware(QueueMiddleware(queue, workers=2))

    async with app:
        pass

    await asyncio.wait_for(queue.join(), timeout=0.1)


async def test_smart_retry_no_jitter() -> None:
    retry = SmartRetry(retries=1, jitter=False, initial_delay=0.1)
    # attempt 1
    delay = retry.compute_delay(1)
    assert delay == 0.1  # noqa: PLR2004
    # attempt 2
    delay = retry.compute_delay(2)
    assert delay == 0.2  # noqa: PLR2004
