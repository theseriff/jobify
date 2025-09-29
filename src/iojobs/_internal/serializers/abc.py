# ruff: noqa: ANN401
# pyright: reportExplicitAny=false

from abc import ABCMeta, abstractmethod
from typing import Any, Protocol


class JobsSerializer(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def dumpb(self, value: Any) -> bytes:
        pass

    @abstractmethod
    def loadb(self, value: bytes) -> Any:
        pass
