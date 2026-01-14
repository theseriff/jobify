import inspect
from typing import Any, no_type_check
from unittest.mock import AsyncMock, Mock

import pytest
from typing_extensions import override

from jobify import INJECT, Job, JobContext, Jobify, State
from jobify._internal.common.constants import EMPTY
from jobify._internal.common.datastructures import RequestState
from jobify._internal.context import inject_context
from jobify._internal.runners import Runnable, create_run_strategy
from jobify.exceptions import JobFailedError
from jobify.middleware import BaseMiddleware, CallNext
from tests.conftest import create_app


class _MyMiddleware(BaseMiddleware):
    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        context.request_state.test = 1
        return await call_next(context)


async def test_injection() -> None:
    app = create_app()
    app.add_middleware(_MyMiddleware())

    job_id: str | None = None
    request_test_num: int | None = None
    state: State | None = None
    ctx: JobContext = EMPTY

    @app.task
    async def some_func(
        job: Job[None] = INJECT,
        request_state: RequestState = INJECT,
        app_state: State = INJECT,
        context: JobContext = INJECT,
    ) -> None:
        nonlocal job_id, request_test_num, state, ctx

        job_id = job.id
        request_test_num = request_state.test
        state = app_state
        ctx = context

    async with app:
        job = await some_func.schedule().delay(0)
        await job.wait()

        assert ctx.job is job
        assert ctx.state is app.state
        assert ctx.request_state.test == 1
        assert state is app.state
        assert job_id == job.id
        assert request_test_num == 1


async def test_injection_wrong_usage() -> None:
    app = create_app()

    @app.task
    @no_type_check
    async def untyped_func(_job=INJECT) -> None:  # noqa: ANN001
        pass

    @app.task
    async def not_exists_type_in_map(_job: Jobify = INJECT) -> None:
        pass

    async with app:
        job1 = await untyped_func.schedule().delay(0)
        job2 = await not_exists_type_in_map.schedule().delay(0)
        await job1.wait()
        await job2.wait()

    with pytest.raises(JobFailedError, match=f"job_id: {job1.id}"):
        job1.result()
    assert "Parameter _job requires" in str(job1.exception)
    assert "Unknown type for injection" in str(job2.exception)


async def test_inject_context_skips_non_inject_parameters(
    amock: AsyncMock,
) -> None:
    strategy = create_run_strategy(amock, Mock(), mode=Mock())

    bound = inspect.signature(amock).bind(normal_param="test")
    runnable = Runnable(strategy, bound)

    mock_context = Mock(spec=JobContext)
    mock_context.runnable = runnable

    inject_context(mock_context)
    result = await runnable()

    amock.assert_awaited_once_with(normal_param="test")
    assert runnable.bound.kwargs.get("normal_param") == "test" == result
