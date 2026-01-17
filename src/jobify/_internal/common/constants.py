from enum import Enum, unique
from typing import Any

from jobify._internal.common.datastructures import EmptyPlaceholder

EMPTY: Any = EmptyPlaceholder()
INFINITY = -1
PATCH_FUNC_NAME = "__jobify_original"
PATCH_CRON_DEF_ID = "__jobify_cron_definition"


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
