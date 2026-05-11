from enum import Enum, unique
from typing import Any, Final

from typing_extensions import Sentinel

from jobify._internal.common.datastructures import EmptyPlaceholder

UNSET: Any = Sentinel("UNSET")
STOP: Any = Sentinel("STOP")
EMPTY: Final[Any] = EmptyPlaceholder()
INFINITY: Final[int] = -1
PATCH_FUNC_NAME: Final[str] = "__jobify_original"
PATCH_CRON_DEF_ID: Final[str] = "__jobify_cron_definition"


@unique
class JobStatus(str, Enum):
    """The status of a job.

    Attributes:
        PENDING: Job is waiting to be processed.
        SCHEDULED: Job is scheduled for future execution.
        RUNNING: Job is currently executing.
        CANCELLED: Job was cancelled.
        SUCCESS: Job completed successfully.
        FAILED: Job failed execution.
        TIMEOUT: Job timed out.
        PERMANENTLY_FAILED: Job failed and exhausted all retry attempts.

    """

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
    """The execution mode of a job.

    Attributes:
        MAIN: Execute in the main event loop.
        THREAD: Execute in a worker thread.
        PROCESS: Execute in a worker process.

    """

    MAIN = "main"
    THREAD = "thread"
    PROCESS = "process"
