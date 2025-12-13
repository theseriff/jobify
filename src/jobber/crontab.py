"""Cron Parser implementation."""

from datetime import datetime
from typing import Final

from crontab import CronTab as _CronTab

from jobber._internal.cron_parser import CronParser


class CronTab(CronParser):
    """Cron expression parser based on the `crontab` library."""

    __slots__: tuple[str, ...] = ("_entry", "_expression")

    def __init__(self, expression: str) -> None:
        """Initialize a CronTab parser.

        Args:
            expression: A cron expression.

        """
        self._expression: str = expression
        self._entry: Final = _CronTab(expression)

    def next_run(self, *, now: datetime) -> datetime:
        """Compute the next scheduled execution time.

        Args:
            now: Current datetime.

        Returns:
            The next run datetime.

        """
        return self._entry.next(now=now, return_datetime=True)  # type: ignore[no-any-return] # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUnknownVariableType]

    def get_expression(self) -> str:
        """Return the original cron expression.

        Returns:
            The cron expression string.

        """
        return self._expression


def create_crontab(expression: str) -> CronTab:
    """Create a CronTab instance.

    Args:
        expression: A cron expression.

    Returns:
        A new CronTab instance.

    """
    return CronTab(expression)
