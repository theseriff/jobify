# pyright: reportExplicitAny=false
from typing import Any
from unittest.mock import Mock

import pytest

from jobber import (
    INJECT,
    ExecutionMode,
    Job,
    Jobber,
    JobContext,
    Runnable,
    State,
)
from jobber._internal.common.constants import EMPTY
from jobber._internal.common.datastructures import RequestState
from jobber._internal.injection import inject_context
from jobber.exceptions import JobFailedError
from jobber.middleware import BaseMiddleware, CallNext


class _MyMiddleware(BaseMiddleware):
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        context.request_state.test = 1
        return await call_next(context)


async def test_injection() -> None:
    jobber = Jobber(middleware=[_MyMiddleware()])

    job_id: str | None = None
    request_test_num: int | None = None
    state: State | None = None
    ctx: JobContext = EMPTY

    @jobber.register
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

    async with jobber:
        job = await some_func.schedule().delay(0)
        await job.wait()

        assert ctx.job is job
        assert ctx.state is jobber.state
        assert ctx.request_state.test == 1
        assert state is jobber.state
        assert job_id == job.id
        assert request_test_num == 1


async def test_injection_wrong_usage() -> None:
    jobber = Jobber()

    @jobber.register
    async def untyped_func(_job=INJECT) -> None:  # type: ignore[no-untyped-def] # pyright: ignore[reportMissingParameterType]  # noqa: ANN001
        pass

    @jobber.register
    async def not_exists_type_in_map(_job: Jobber = INJECT) -> None:
        pass

    async with jobber:
        job1 = await untyped_func.schedule().delay(0)
        job2 = await not_exists_type_in_map.schedule().delay(0)
        await job1.wait()
        await job2.wait()

    with pytest.raises(JobFailedError, match=f"job_id: {job1.id}"):
        job1.result()
    assert "Parameter _job requires" in str(job1.exception)
    assert "Unknown type for injection" in str(job2.exception)


async def test_inject_context_skips_non_inject_parameters() -> None:
    func_mock = Mock(return_value="test")
    runnable = Runnable(func_mock, ExecutionMode.MAIN, normal_param="test")
    mock_context = Mock(spec=JobContext)
    inject_context(runnable, mock_context)

    assert runnable.kwargs.get("normal_param") == "test" == runnable()
