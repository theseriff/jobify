from __future__ import annotations

from typing import Any, Protocol


class Loader(Protocol):
    def load(self, data: Any, tp: Any) -> Any:  # noqa: ANN401
        raise NotImplementedError


class Dumper(Protocol):
    def dump(self, data: Any, tp: Any) -> Any:  # noqa: ANN401
        raise NotImplementedError
