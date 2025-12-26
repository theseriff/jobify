from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from typing import NamedTuple, Protocol

from jobber._internal.common.constants import JobStatus


class ScheduledJob(NamedTuple):
    job_id: str
    func_name: str
    message: bytes
    status: JobStatus


class Storage(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def startup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_schedules(self) -> Iterable[ScheduledJob]:
        raise NotImplementedError

    @abstractmethod
    async def add_schedule(self, scheduled: ScheduledJob) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_schedule(self, job_id: str) -> None:
        raise NotImplementedError
