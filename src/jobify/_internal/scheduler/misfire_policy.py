from datetime import timedelta
from enum import Enum
from typing import NamedTuple

from typing_extensions import override


class GracePolicy(NamedTuple):
    value: timedelta

    @override
    def __str__(self) -> str:
        return f"<{type(self).__name__} value={self.value}>"


class MisfirePolicy(str, Enum):
    ALL = "all"
    SKIP = "skip"
    ONCE = "once"

    @staticmethod
    def GRACE(t: timedelta, /) -> GracePolicy:  # noqa: N802
        return GracePolicy(t)
