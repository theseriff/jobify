from __future__ import annotations

from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class Loader(Protocol):
    """Interface for loading data into typed objects."""

    def load(self, data: Any, tp: type[T], /) -> T:  # noqa: ANN401
        """Load data into the specified type `tp`."""
        raise NotImplementedError


class Dumper(Protocol):
    """Interface for dumping objects into a serializable format."""

    def dump(self, data: Any, tp: Any, /) -> Any:  # noqa: ANN401
        """Dump object `data` based on type `tp`."""
        raise NotImplementedError
