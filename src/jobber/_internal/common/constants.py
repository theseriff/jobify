from enum import Enum, unique
from typing import Any

from jobber._internal.common.datastructures import EmptyPlaceholder

EMPTY: Any = EmptyPlaceholder()


@unique
class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    CANCELLED = "cancelled"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@unique
class RunMode(str, Enum):
    MAIN = "main"
    THREAD = "thread"
    PROCESS = "process"
