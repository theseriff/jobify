# pyright: reportExplicitAny=false
import functools
from typing import Any
from unittest.mock import Mock

import pytest

from jobber import INJECT, Job, Jobber, JobContext, State
from jobber._internal.common.constants import EMPTY
from jobber._internal.common.datastructures import RequestState
from jobber._internal.injection import inject_context
from jobber.middleware import BaseMiddleware, CallNext


class _MyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        call_next: CallNext[Any],
        context: JobContext,
    ) -> Any:  # noqa: ANN401
        context.request_state.test = 1
        return await call_next(context)


async def test_injection(jobber: Jobber) -> None:
    jobber.middleware.use(_MyMiddleware())

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

    job = await some_func.schedule().delay(0)
    await job.wait()

    assert ctx.job is job
    assert ctx.state is jobber.state
    assert ctx.request_state.test == 1
    assert state is jobber.state
    assert job_id == job.id
    assert request_test_num == 1


async def test_injection_wrong_usage() -> None:
    async def untyped_func(_job=INJECT) -> None:  # type: ignore[no-untyped-def] # pyright: ignore[reportMissingParameterType]  # noqa: ANN001
        pass

    async def not_exists_type_in_map(_job: Jobber = INJECT) -> None:
        pass

    partial = functools.partial(untyped_func)
    with pytest.raises(ValueError, match="Parameter _job requires"):
        inject_context(partial, Mock())

    partial = functools.partial(not_exists_type_in_map)
    with pytest.raises(ValueError, match="Unknown type for injection"):
        inject_context(partial, Mock())
