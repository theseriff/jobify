import warnings
from enum import Enum, unique
from typing import Any

from jobber._internal.common.datastructures import EmptyPlaceholder

EMPTY: Any = EmptyPlaceholder()


@unique
class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@unique
class RunMode(str, Enum):
    MAIN = "main"
    THREAD = "thread"
    PROCESS = "process"


def get_run_mode(mode: RunMode, *, is_async: bool) -> RunMode:
    if is_async:
        if mode in (RunMode.PROCESS, RunMode.THREAD):
            msg = (
                "Async functions are always done in the main loop."
                " This mode (PROCESS/THREAD) is not used."
            )
            warnings.warn(msg, category=RuntimeWarning, stacklevel=3)
        return RunMode.MAIN
    if mode is EMPTY:
        return RunMode.THREAD
    return mode
