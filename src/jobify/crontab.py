"""Cron Parser implementation."""

from datetime import datetime
from typing import TYPE_CHECKING, Protocol, cast

from crontab import CronTab as _CronTab  # pyrefly: ignore [untyped-import]
from typing_extensions import override

from jobify._internal.cron_parser import CronParser

if TYPE_CHECKING:

    class CronTabStub(Protocol):
        """Typed subset of the third-party `crontab.CronTab` API we rely on."""

        def next(self, now: datetime, *, return_datetime: bool) -> datetime:
            """Return the next scheduled run timestamp from `now`."""
            ...


class CronTab(CronParser):
    """Cron expression parser based on the `crontab` library."""

    __slots__: tuple[str, ...] = ("_entry",)

    def __init__(self, expression: str) -> None:
        """Initialize a CronTab parser."""
        self._entry = cast("CronTabStub", _CronTab(expression))

    @override
    def next_run(self, *, now: datetime) -> datetime:
        """Compute the next scheduled execution time."""
        return self._entry.next(now=now, return_datetime=True)


def create_crontab(expression: str) -> CronTab:
    """Create a CronTab instance."""
    return CronTab(expression)
