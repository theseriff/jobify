from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Protocol, TypeAlias

SerializableTypes: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | bytes
    | set["SerializableTypes"]
    | list["SerializableTypes"]
    | tuple["SerializableTypes", ...]
    | dict[str, "SerializableTypes"]
)


class JobsSerializer(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def dumpb(self, data: SerializableTypes) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def loadb(self, data: bytes) -> SerializableTypes:
        raise NotImplementedError
