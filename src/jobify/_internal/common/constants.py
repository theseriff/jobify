from enum import Enum, unique
from typing import Any

from jobify._internal.common.datastructures import EmptyPlaceholder

EMPTY: Any = EmptyPlaceholder()
INFINITY = -1
PATCH_SUFFIX = "__jobify_original"


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
