from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from jobify._internal.common.datastructures import RequestState, State
    from jobify._internal.configuration import JobifyConfiguration, RouteOptions
    from jobify._internal.inspection import FuncSpec
    from jobify._internal.message import Triggers
    from jobify._internal.runners import Runnable
    from jobify._internal.scheduler.job import Job
    from jobify._internal.scheduler.scheduler import ScheduleBuilder
    from jobify.jobify import Jobify


class OuterContext:
    """Context object passed to middleware during the scheduling process.

    This object holds all information required to inspect, modify, or
    intercept a job before it is officially scheduled.

    Attributes:
        app: The Jobify application instance.
        job: The job instance being scheduled.
        state: The global application state.
        trigger: The trigger mechanism (e.g., Cron, Push).
        runnable: The runnable component (function/method) being scheduled.
        arguments: The arguments bound to the job function.
        func_spec: Inspection details of the job function.
        is_force: Whether the job is forced to run.
        is_persist: Whether the job should be persisted to storage.
        is_replace: Whether the job replaces an existing one.
        route_options: Configuration options for the route.
        jobify_config: Global Jobify configuration.
        request_state: State specific to the current request.
        persist_job_hook: Callback to persist the job.
        schedule_hook: Callback to schedule the job.
        schedule_builder: Builder used to construct the schedule.

    """

    __slots__: tuple[str, ...] = (
        "app",
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

    # ... (rest of the __init__ remains the same)
    def __init__(  # noqa: PLR0913
        self,
        *,
        app: Jobify,
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
        self.app = app
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
    """Context object injected into jobs at runtime.

    Provides access to job execution context, allowing jobs to inspect
    their configuration, state, and scheduling builder.

    Attributes:
        app: The Jobify application instance.
        job: The job instance.
        state: The global application state.
        runnable: The runnable component.
        request_state: State specific to the current request.
        route_options: Configuration options for the route.
        jobify_config: Global Jobify configuration.
        schedule_builder: Builder used to construct the schedule.

    """

    app: Jobify
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
        elif (field_name := CONTEXT_TYPE_MAP.get(_resolve_type_key(tp))) is not None:
            val = getattr(context, field_name)
        else:
            msg = (
                f"Unknown type for injection: {tp}. "
                f"Available types: {list(CONTEXT_TYPE_MAP.keys())}"
            )
            raise ValueError(msg)
        arguments[name] = val
