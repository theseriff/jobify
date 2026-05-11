import re
from abc import ABCMeta, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple, Protocol

from jobify._internal.common.constants import JobStatus


class ScheduledJob(NamedTuple):
    """Represents a job persisted in storage.

    Attributes:
        job_id: Unique identifier of the job.
        name: Name of the job route.
        message: Serialized job message bytes.
        status: Current status of the job in storage.
        next_run_at: The next scheduled execution time.

    """

    job_id: str
    name: str
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
    """Storage interface for job persistence."""

    @abstractmethod
    async def startup(self) -> None:
        """Initialize the storage backend."""
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        """Close the storage backend."""
        raise NotImplementedError

    @abstractmethod
    async def get_schedules(self) -> Sequence[ScheduledJob]:
        """Retrieve all currently scheduled jobs."""
        raise NotImplementedError

    @abstractmethod
    async def add_schedule(self, *scheduled: ScheduledJob) -> None:
        """Persist new job schedules."""
        raise NotImplementedError

    @abstractmethod
    async def delete_schedule(self, job_id: str) -> None:
        """Delete a job schedule by ID."""
        raise NotImplementedError

    @abstractmethod
    async def delete_schedule_many(self, job_ids: Sequence[str]) -> None:
        """Delete multiple job schedules by IDs."""
        raise NotImplementedError
