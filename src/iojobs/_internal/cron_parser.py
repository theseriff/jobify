from datetime import datetime
from typing import Final

from crontab import CronTab


class CronParser:
    __slots__: tuple[str, ...] = ("_entry", "_expression")

    def __init__(self, expression: str) -> None:
        self._expression: Final = expression
        self._entry: Final = CronTab(expression)

    def next_run(self, *, now: datetime) -> datetime:
        return self._entry.next(now=now, return_datetime=True)  # type: ignore[no-any-return] # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUnknownVariableType]
