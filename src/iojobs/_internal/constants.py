# pyright: reportExplicitAny=false
from enum import Enum, unique
from typing import Any


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


class EmptyPlaceholder:  # pragma: no cover
    def __repr__(self) -> str:
        return "EMPTY"

    def __hash__(self) -> int:
        return hash("EMPTY")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__)

    def __bool__(self) -> bool:
        return False


EMPTY: Any = EmptyPlaceholder()
FAILED: Any = EmptyPlaceholder()
