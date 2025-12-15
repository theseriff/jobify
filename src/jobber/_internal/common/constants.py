from enum import Enum, unique
from typing import Any, cast

from jobber._internal.common.datastructures import EmptyPlaceholder

EMPTY: Any = EmptyPlaceholder()
INFINITY = cast("int", float("inf"))


@unique
class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    CANCELLED = "cancelled"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PERMANENTLY_FAILED = "permanently_failed"


@unique
class RunMode(str, Enum):
    MAIN = "main"
    THREAD = "thread"
    PROCESS = "process"
