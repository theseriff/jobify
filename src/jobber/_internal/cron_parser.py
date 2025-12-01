from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class CronParser(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, expression: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def next_run(self, *, now: datetime) -> datetime:
        raise NotImplementedError

    @abstractmethod
    def get_expression(self) -> str:
        raise NotImplementedError
