from __future__ import annotations

from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class Loader(Protocol):
    def load(self, data: Any, tp: type[T], /) -> T:  # noqa: ANN401
        raise NotImplementedError


class Dumper(Protocol):
    def dump(self, data: Any, tp: Any, /) -> Any:  # noqa: ANN401
        raise NotImplementedError
