from dataclasses import dataclass
from typing import Any

from jobify._internal.common.datastructures import RequestState, State
from jobify._internal.configuration import (
    JobifyConfiguration,
    RouteOptions,
)
from jobify._internal.runners import Runnable
from jobify._internal.scheduler.job import Job


@dataclass(slots=True, kw_only=True)
class JobContext:
    job: Job[Any]
    state: State
    runnable: Runnable[Any]
    request_state: RequestState
    route_options: RouteOptions
    jobify_config: JobifyConfiguration
