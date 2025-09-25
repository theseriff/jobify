from datetime import datetime
from zoneinfo import ZoneInfo

from iojobs._internal.cron_parser import CronParser


def test_cronparser() -> None:
    cron = CronParser("@daily")
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    next_run = cron.next_run(now=now)
    expected_delay = now.replace(
        day=now.day + 1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    assert next_run == expected_delay
