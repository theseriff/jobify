from typing import Any, no_type_check
from unittest.mock import Mock

import pytest
from typing_extensions import override

from jobify import (
    INJECT,
    Job,
    JobContext,
    Jobify,
    Runnable,
    ScheduleBuilder,
    State,
)
from jobify._internal.common.datastructures import RequestState
from jobify._internal.configuration import JobifyConfiguration, RouteOptions
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

    mock = Mock()
    contexts: list[JobContext] = []

    @app.task
    async def some_func(  # noqa: PLR0913
        job: Job[None] = INJECT,
        app_state: State = INJECT,
        runnable: Runnable[None] = INJECT,
        request_state: RequestState = INJECT,
        route_options: RouteOptions = INJECT,
        jobify_config: JobifyConfiguration = INJECT,
        context: JobContext = INJECT,
        builder: ScheduleBuilder[None] = INJECT,
    ) -> None:
        mock(
            job,
            app_state,
            runnable,
            request_state,
            route_options,
            jobify_config,
            context,
            builder,
        )
        contexts.append(context)

    async with app:
        builder = some_func.schedule()
        job = await builder.push()
        await job.wait()

    context = contexts.pop()
    assert isinstance(context, JobContext)
    mock.assert_called_once_with(
        job,
        {},
        builder._runnable,
        {"test": 1},
        builder.route_options,
        builder._configs,
        context,
        builder,
    )


async def test_injection_wrong_usage() -> None:
    app = create_app()

    with pytest.raises(
        ValueError,
        match="Parameter '_job' requires a type annotation for INJECT",
    ):

        @app.task
        @no_type_check
        async def untyped_func(_job=INJECT) -> None:  # noqa: ANN001
            pass

    @app.task
    async def not_exists_type_in_map(_job: Jobify = INJECT) -> None:
        pass

    async with app:
        job = await not_exists_type_in_map.schedule().delay(0)
        await job.wait()

    assert "Unknown type for injection" in str(job.exception)


async def test_func_without_inject_params_executes_correctly() -> None:
    app = create_app()

    mock = Mock()

    @app.task
    async def func_without_inject(normal_param: str) -> None:
        mock(normal_param)

    async with app:
        job = await func_without_inject.schedule("hello").push()
        await job.wait()

    mock.assert_called_once_with("hello")
