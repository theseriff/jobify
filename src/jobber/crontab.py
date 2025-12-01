"""Cron Parser implementation."""

from datetime import datetime
from typing import Final

from crontab import CronTab

from jobber._internal.cron_parser import CronParser


class Crontab(CronParser):
    """A cron expression parser implementation for Jobber.

    This class extends the `CronParser` abstract base class and utilizes
    the `crontab` library to parse cron expressions and calculate
    the next scheduled run time.
    """

    __slots__: tuple[str, ...] = ("_entry", "_expression")

    def __init__(self, expression: str) -> None:
        """Initialize a `Cronier` instance.

        Args:
            expression: cron expression.

        """
        self._expression: str = expression
        self._entry: Final = CronTab(expression)

    def next_run(self, *, now: datetime) -> datetime:
        """Return the next run `datetime`.

        Args:
            now: current time.

        Returns:
            The next run `datetime`.

        """
        return self._entry.next(now=now, return_datetime=True)  # type: ignore[no-any-return] # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUnknownVariableType]

    def get_expression(self) -> str:
        """Return a cron expression.

        Returns:
            A cron expression.

        """
        return self._expression
