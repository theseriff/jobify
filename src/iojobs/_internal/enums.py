from enum import Enum, unique


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
