import asyncio
import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import (
    Any,
    NamedTuple,
    final,
    get_origin,
    get_type_hints,
)

from jobify._internal.common.datastructures import RequestState, State
from jobify._internal.common.types import ExceptionHandlers
from jobify._internal.configuration import JobifyConfiguration, RouteOptions
from jobify._internal.inspection import FuncSpec
from jobify._internal.message import Triggers
from jobify._internal.runners import Runnable
from jobify._internal.scheduler.job import Job


@final
class OuterContext:
    __slots__: tuple[str, ...] = (
        "arguments",
        "func_spec",
        "is_force",
        "is_persist",
        "is_replace",
        "job",
        "jobify_config",
        "persist_job_hook",
        "request_state",
        "route_options",
        "runnable",
        "schedule_hook",
        "state",
        "trigger",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        job: Job[Any],
        state: State,
        trigger: Triggers,
        runnable: Runnable[Any],
        arguments: dict[str, Any],
        func_spec: FuncSpec[Any],
        is_force: bool,
        is_persist: bool,
        is_replace: bool,
        route_options: RouteOptions,
        jobify_config: JobifyConfiguration,
        request_state: RequestState,
        persist_job_hook: Callable[[str, datetime, Triggers], Awaitable[None]],
        schedule_hook: Callable[[], asyncio.Handle],
    ) -> None:
        self.job = job
        self.state = state
        self.trigger = trigger
        self.runnable = runnable
        self.arguments = arguments
        self.func_spec = func_spec
        self.is_force = is_force
        self.is_persist = is_persist
        self.is_replace = is_replace
        self.route_options = route_options
        self.jobify_config = jobify_config
        self.request_state = request_state
        self.persist_job_hook = persist_job_hook
        self.schedule_hook = schedule_hook


class JobContext(NamedTuple):
    job: Job[Any]
    state: State
    runnable: Runnable[Any]
    request_state: RequestState
    route_options: RouteOptions
    jobify_config: JobifyConfiguration
    exception_handlers: ExceptionHandlers


INJECT: Any = object()
CONTEXT_TYPE_MAP = {
    get_origin(field_type) or field_type: field_name
    for field_name, field_type in get_type_hints(JobContext).items()
}


def inject_context(context: JobContext) -> None:
    bound = context.runnable.bound
    arguments = bound.arguments

    for name, param in bound.signature.parameters.items():
        if param.default is not INJECT:
            continue

        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            msg = f"Parameter {name} requires a type annotation for INJECT"
            raise ValueError(msg)

        tp = get_origin(annotation) or annotation
        if tp is JobContext:
            val = context
        elif field_name := CONTEXT_TYPE_MAP.get(tp):
            val = getattr(context, field_name)
        else:
            msg = (
                f"Unknown type for injection: {tp}. "
                f"Available types: {list(CONTEXT_TYPE_MAP.keys())}"
            )
            raise ValueError(msg)
        arguments[name] = val
