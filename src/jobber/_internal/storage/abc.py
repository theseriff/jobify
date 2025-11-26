from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from jobber._internal.common.constants import ExecutionMode, JobStatus


@dataclass(slots=True, kw_only=True)
class JobStored:
    job_id: str
    func_id: str
    exec_at_timestamp: float
    status: JobStatus
    func_args: bytes
    func_kwargs: bytes
    exec_mode: ExecutionMode
    created_at: datetime
    updated_at: datetime
    cron_expression: str | None = None
    error: str | None = None


@runtime_checkable
class JobRepository(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def load_all(self) -> Iterable[JobStored]:
        raise NotImplementedError
