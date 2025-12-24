from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from jobber._internal.common.constants import JobStatus


@dataclass(slots=True, kw_only=True)
class ScheduledJob:
    job_id: str
    route_name: str
    message: bytes
    status: JobStatus


class Storage(Protocol, metaclass=ABCMeta):
    @abstractmethod
    async def all(self) -> Iterable[ScheduledJob]:
        raise NotImplementedError

    @abstractmethod
    async def add(self, scheduled: ScheduledJob) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, job_id: str) -> None:
        raise NotImplementedError
