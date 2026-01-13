import re
from abc import ABCMeta, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple, Protocol

from jobify._internal.common.constants import JobStatus


class ScheduledJob(NamedTuple):
    job_id: str
    func_name: str
    message: bytes
    status: JobStatus
    next_run_at: datetime


def validate_table_name(table_name: str) -> None:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        msg = (
            f"Invalid table name: {table_name!r}. "
            f"Must contain only letters, digits, and underscores."
        )
        raise ValueError(msg)


class Storage(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def startup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_schedules(self) -> Sequence[ScheduledJob]:
        raise NotImplementedError

    @abstractmethod
    async def add_schedule(self, *scheduled: ScheduledJob) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_schedule(self, job_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_schedule_many(self, job_ids: Sequence[str]) -> None:
        raise NotImplementedError
