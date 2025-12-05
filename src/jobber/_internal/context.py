from dataclasses import dataclass
from typing import Any

from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.configuration import (
    JobberConfiguration,
    RouteConfiguration,
)
from jobber._internal.runner.job import Job
from jobber._internal.runner.runners import Runnable


@dataclass(slots=True, kw_only=True)
class JobContext:
    job: Job[Any]
    state: State
    request_state: RequestState
    runnable: Runnable[Any]
    route_config: RouteConfiguration
    jobber_config: JobberConfiguration
