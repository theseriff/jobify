from typing import Any, NewType


class EmptyPlaceholder:
    def __repr__(self) -> str:
        return "EMPTY"

    def __hash__(self) -> int:
        return hash("EMPTY")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__)

    def __bool__(self) -> bool:
        return False


EMPTY: Any = EmptyPlaceholder()  # pyright: ignore[reportExplicitAny]
FuncID = NewType("FuncID", str)
