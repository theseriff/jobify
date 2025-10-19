from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from iojobs import JobScheduler
from iojobs._internal.cron_parser import CronParser


def test_cronparser() -> None:
    cron = CronParser("@daily")
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    next_run = cron.next_run(now=now)
    expected_run = now.replace(
        day=now.day + 1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    assert next_run == expected_run


async def test_cron_reschedule(scheduler: JobScheduler, now: datetime) -> None:
    @scheduler.register
    def t(name: str) -> str:
        return f"hello, {name}!"

    with mock.patch.object(CronParser, "next_run", return_value=now):
        job = await t.schedule("Biba").cron("* * * * *", now=now)

    prev_job_id = job.id
    await job.wait()
    new_job_id = job.id

    assert job.result() == "hello, Biba!"
    assert prev_job_id != new_job_id
