# pyright: reportImportCycles=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple, final

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from jobify._internal.common.datastructures import RequestState, State
    from jobify._internal.configuration import (
        JobifyConfiguration,
        RouteOptions,
    )
    from jobify._internal.inspection import FuncSpec
    from jobify._internal.message import Triggers
    from jobify._internal.runners import Runnable
    from jobify._internal.scheduler.job import Job
    from jobify._internal.scheduler.scheduler import ScheduleBuilder


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
        "schedule_builder",
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
        schedule_builder: ScheduleBuilder[Any],
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
        self.schedule_builder = schedule_builder


class JobContext(NamedTuple):
    job: Job[Any]
    state: State
    runnable: Runnable[Any]
    request_state: RequestState
    route_options: RouteOptions
    jobify_config: JobifyConfiguration
    schedule_builder: ScheduleBuilder[Any]


def _resolve_type_key(field_type: Any) -> str:  # noqa: ANN401
    """Extract a string key from a type annotation for matching.

    Handles both resolved types and forward references without triggering
    circular imports.
    """
    # Check if it's a ForwardRef (unresolved string annotation)
    if hasattr(field_type, "__forward_arg__"):
        # Extract base type name from forward ref
        forward_arg: str = field_type.__forward_arg__
        return forward_arg.split("[", 1)[0]
    # For resolved types, use __name__ or __qualname__
    return getattr(
        field_type,
        "__qualname__",
        getattr(field_type, "__name__", str(field_type)),
    )


def _make_type_map(tp: type[Any]) -> dict[str, str]:
    """Build a mapping from type name to field name for injection lookups."""
    return {
        _resolve_type_key(field_type): field_name
        for field_name, field_type in tp.__annotations__.items()
    }


CONTEXT_TYPE_MAP = _make_type_map(JobContext)


def inject_context(context: JobContext) -> None:
    runnable = context.runnable
    arguments = runnable.bound.arguments
    for name, tp in runnable.func_spec.inject_params.items():
        if tp is JobContext:
            val = context
        elif (
            field_name := CONTEXT_TYPE_MAP.get(_resolve_type_key(tp))
        ) is not None:
            val = getattr(context, field_name)
        else:
            msg = (
                f"Unknown type for injection: {tp}. "
                f"Available types: {list(CONTEXT_TYPE_MAP.keys())}"
            )
            raise ValueError(msg)
        arguments[name] = val
