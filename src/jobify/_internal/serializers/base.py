from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any, Protocol, TypeAlias

JSONCompat: TypeAlias = (
    dict[str, "JSONCompat"] | list["JSONCompat"] | str | int | float | bool | None
)


class Serializer(Protocol, metaclass=ABCMeta):
    """Interface for serializing and deserializing job messages."""

    @abstractmethod
    def dumpb(self, data: Any) -> bytes:  # noqa: ANN401
        """Serialize data to bytes."""
        raise NotImplementedError

    @abstractmethod
    def loadb(self, data: bytes) -> Any:  # noqa: ANN401
        """Deserialize data from bytes."""
        raise NotImplementedError
