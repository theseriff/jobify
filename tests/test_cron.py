from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from jobber import Jobber
from jobber._internal.cron_parser import CronParser


def test_cronparser() -> None:
    cron = CronParser("@daily")
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    next_run = cron.next_run(now=now)
    expected_run = (now + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    assert next_run == expected_run


async def test_cron_reschedule(jobber: Jobber, now: datetime) -> None:
    @jobber.register
    def t(name: str) -> str:
        return f"hello, {name}!"

    with mock.patch.object(CronParser, "next_run", return_value=now):
        job = await t.schedule("Biba").cron("* * * * *", now=now)

    cur_exec_at = job.exec_at
    await job.wait()
    next_exec_at = job.exec_at

    assert job.result() == "hello, Biba!"
    assert cur_exec_at != next_exec_at
