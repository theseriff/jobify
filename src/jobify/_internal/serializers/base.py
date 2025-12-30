from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any, Protocol, TypeAlias

JSONCompat: TypeAlias = (
    dict[str, "JSONCompat"]
    | list["JSONCompat"]
    | str
    | int
    | float
    | bool
    | None
)


class Serializer(Protocol, metaclass=ABCMeta):
    @abstractmethod
    def dumpb(self, data: Any) -> bytes:  # noqa: ANN401
        raise NotImplementedError

    @abstractmethod
    def loadb(self, data: bytes) -> Any:  # noqa: ANN401
        raise NotImplementedError
