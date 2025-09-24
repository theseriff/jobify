from datetime import datetime
from zoneinfo import ZoneInfo

from taskaio._internal.cron_parser import CronParser


def test_cronparser() -> None:
    cron = CronParser("@daily")
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    midnight = now.replace(
        day=now.day + 1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    expected_delay = midnight
    next_run = cron.next_run(now=now)
    assert next_run == expected_delay
