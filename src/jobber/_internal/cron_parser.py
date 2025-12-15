from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import Protocol, TypeAlias, runtime_checkable

FactoryCron: TypeAlias = Callable[[str], "CronParser"]


@runtime_checkable
class CronParser(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def next_run(self, *, now: datetime) -> datetime:
        raise NotImplementedError
