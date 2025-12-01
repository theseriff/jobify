# ruff: noqa: ANN401
from __future__ import annotations

from collections import UserDict
from typing import Any


class EmptyPlaceholder:
    def __repr__(self) -> str:
        return "EMPTY"

    def __hash__(self) -> int:
        return hash("EMPTY")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__)

    def __bool__(self) -> bool:
        return False


class State(UserDict[str, Any]):
    """An object that can be used to store arbitrary state."""

    data: dict[str, Any]
    __slots__: tuple[str, ...] = ("data",)

    def __init__(self, state: dict[str, Any] | None = None) -> None:  # pyright: ignore[reportMissingSuperCall]
        object.__setattr__(self, "data", state or {})

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def __getattr__(self, key: str) -> Any:
        try:
            return self.data[key]
        except KeyError as exc:
            message = (
                f"{self.__class__.__name__!r} object has no attribute {key!r}"
            )
            raise AttributeError(message) from exc

    def __delattr__(self, key: str) -> None:
        del self[key]

    def __str__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}({super().__str__()})"


class RequestState(State): ...
