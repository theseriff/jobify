from enum import Enum, unique
from typing import Any

from jobber._internal.common.datastructures import EmptyPlaceholder


@unique
class ExecutionMode(str, Enum):
    MAIN = "main"
    THREAD = "thread"
    PROCESS = "process"


@unique
class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SKIPPED = "skipped"
    CANCELED = "canceled"
    SUCCESS = "success"
    FAILED = "failed"


EMPTY: Any = EmptyPlaceholder()
