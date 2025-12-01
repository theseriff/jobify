from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jobber import Jobber
from jobber._internal.cron_parser import CronParser
from jobber.crontab import Crontab


def test_cronparser() -> None:
    cron = Crontab("@daily")
    now = datetime.now(tz=ZoneInfo("Europe/Moscow"))
    next_run = cron.next_run(now=now)
    expected_run = (now + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    assert cron.get_expression() == "@daily"
    assert next_run == expected_run


async def test_cron_reschedule(
    now: datetime,
    cron_parser_cls: type[CronParser],
) -> None:
    jobber = Jobber(cron_parser_cls=cron_parser_cls)

    @jobber.register
    def t(name: str) -> str:
        return f"hello, {name}!"

    async with jobber:
        job = await t.schedule("Biba").cron("* * * * *", now=now)

        cur_exec_at = job.exec_at
        await job.wait()
        next_exec_at = job.exec_at

        assert job.result() == "hello, Biba!"
        assert cur_exec_at != next_exec_at
