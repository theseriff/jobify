from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.configuration import (
    JobberConfiguration,
    RouteOptions,
)
from jobber._internal.runner.job import Job
from jobber._internal.runner.runners import Runnable

JobberApp: TypeAlias = Callable[["JobContext"], Any]


@dataclass(slots=True, kw_only=True)
class JobContext:
    job: Job[Any]
    state: State
    request_state: RequestState
    runnable: Runnable[Any]
    route_config: RouteOptions
    jobber_config: JobberConfiguration
