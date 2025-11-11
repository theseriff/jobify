# pyright: reportExplicitAny=false
from enum import Enum, unique
from typing import Any

from iojobs._internal.datastructures import EmptyPlaceholder


@unique
class ExecutionMode(str, Enum):
    MAIN = "main"
    THREAD = "thread"
    PROCESS = "process"


@unique
class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    CANCELED = "canceled"
    SUCCESS = "success"
    FAILED = "failed"


EMPTY: Any = EmptyPlaceholder()
FAILED: Any = EmptyPlaceholder()
