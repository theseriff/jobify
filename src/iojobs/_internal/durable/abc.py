from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from iojobs._internal.enums import ExecutionMode, JobStatus


@dataclass(slots=True, kw_only=True)
class JobPersisted:
    job_id: str
    func_id: str
    exec_at_timestamp: float
    status: JobStatus
    func_args: bytes
    func_kwargs: bytes
    execution_mode: ExecutionMode
    created_at: datetime
    updated_at: datetime
    cron_expression: str | None = None
    error: str | None = None


class JobRepository(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def load_all(self) -> tuple[JobPersisted]:
        raise NotImplementedError
