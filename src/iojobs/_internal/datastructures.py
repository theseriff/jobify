# pyright: reportExplicitAny=false
from collections.abc import Mapping
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


class State:
    """
    An object that can be used to store arbitrary state.

    Used for `request.state` and `app.state`.
    """

    _state: dict[str, Any]  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        if state is None:
            state = {}
        super().__setattr__("_state", state)

    def __setattr__(self, key: Any, value: Any) -> None:  # noqa: ANN401
        self._state[key] = value

    def __getattr__(self, key: Any) -> Any:  # noqa: ANN401
        try:
            return self._state[key]
        except KeyError as exc:
            message = (
                f"{self.__class__.__name__!r} object has no attribute {key!r}"
            )
            raise AttributeError(message) from exc

    def __delattr__(self, key: Any) -> None:  # noqa: ANN401
        del self._state[key]

    def update(self, state: Mapping[str, Any]) -> None:
        self._state.update(state)
