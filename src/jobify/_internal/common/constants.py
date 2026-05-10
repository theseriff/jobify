from enum import Enum, unique
from typing import Any, Final

from jobify._internal.common.datastructures import EmptyPlaceholder

EMPTY: Final[Any] = EmptyPlaceholder()
INFINITY: Final[int] = -1
PATCH_FUNC_NAME: Final[str] = "__jobify_original"
PATCH_CRON_DEF_ID: Final[str] = "__jobify_cron_definition"


@unique
class JobStatus(str, Enum):
    PENDING = "pending"
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
