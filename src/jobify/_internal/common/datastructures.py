# ruff: noqa: ANN401
from __future__ import annotations

from collections import UserDict
from typing import Any

from typing_extensions import override


class State(UserDict[str, Any]):
    """An object that can be used to store arbitrary state.

    This class provides dictionary-like access to state data, allowing for both
    key-based and attribute-based access.

    Args:
        state: Initial state dictionary.

    """

    data: dict[str, Any]
    __slots__: tuple[str] = ("data",)

    def __init__(self, state: dict[str, Any] | None = None) -> None:  # pyright: ignore[reportMissingSuperCall]
        object.__setattr__(self, "data", state or {})

    @override
    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def __getattr__(self, key: str) -> Any:
        try:
            return self.data[key]
        except KeyError as exc:
            message = f"{self.__class__.__name__!r} object has no attribute {key!r}"
            raise AttributeError(message) from exc

    @override
    def __delattr__(self, key: str) -> None:
        del self[key]

    @override
    def __str__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}({super().__str__()})"


class RequestState(State):
    """An object that can be used to store state specific to a request."""
