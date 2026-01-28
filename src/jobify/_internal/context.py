import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, get_origin, get_type_hints

from jobify._internal.common.datastructures import RequestState, State
from jobify._internal.configuration import JobifyConfiguration, RouteOptions
from jobify._internal.inspection import FuncSpec
from jobify._internal.message import AtArguments, CronArguments
from jobify._internal.runners import Runnable
from jobify._internal.scheduler.job import Job


@dataclass(slots=True, kw_only=True)
class OuterContext:
    job: Job[Any]
    state: State
    trigger: AtArguments | CronArguments
    runnable: Runnable[Any]
    arguments: dict[str, Any]
    func_spec: FuncSpec[Any]
    is_force: bool
    is_persist: bool
    is_replace: bool
    route_options: RouteOptions
    jobify_config: JobifyConfiguration
    request_state: RequestState
    persist_job_hook: Callable[
        [str, datetime, AtArguments | CronArguments],
        Awaitable[None],
    ]
    schedule_hook: Callable[[], asyncio.Handle]


@dataclass(slots=True, kw_only=True)
class JobContext:
    job: Job[Any]
    state: State
    runnable: Runnable[Any]
    request_state: RequestState
    route_options: RouteOptions
    jobify_config: JobifyConfiguration


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
