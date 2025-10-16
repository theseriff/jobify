# pyright: reportPrivateUsage=false
from datetime import datetime
from unittest import mock

import pytest

from iojobs import JobScheduler
from iojobs._internal.enums import JobStatus
from iojobs._internal.exceptions import JobFailedError


async def test_job(scheduler: JobScheduler) -> None:
    @scheduler.register(func_name="t")
    def t(num: int) -> int:
        return num + 1

    job1 = await t.schedule(1).delay(0)
    job2 = await t.schedule(1).delay(0.01)
    assert str(job1).startswith(f"Job(instance_id={id(job1)}")
    assert str(job2).startswith(f"Job(instance_id={id(job2)}")
    assert job2 > job1

    await job1.wait()
    with pytest.warns(RuntimeWarning, match="Job is already done"):
        await job1.wait()

    job2.cancel()
    assert job2.is_done()
    assert job2.status is JobStatus.CANCELED
    assert job2 not in job2._job_registered
    assert job2._timer_handler.cancelled()


async def test_job_runner_hooks(scheduler: JobScheduler) -> None:
    @scheduler.register(func_name="t")
    def t(num: int) -> int:
        return 10 // num

    expected_on_success = 0
    msg_or_error: Exception = Exception()

    def on_success(num: int) -> None:
        nonlocal expected_on_success
        expected_on_success = num

    def on_error(exc: Exception) -> None:
        nonlocal msg_or_error
        msg_or_error = exc

    job1 = await t.schedule(1).on_success(on_success).delay(0)
    job2 = await t.schedule(0).on_error(on_error).delay(0)
    await job1.wait()
    await job2.wait()

    with pytest.raises(JobFailedError, match="division"):
        assert job2.result()

    assert job1.result() == expected_on_success
    assert type(msg_or_error) is ZeroDivisionError


async def test_job_runner_hooks_wrong_usage(scheduler: JobScheduler) -> None:
    @scheduler.register(func_name="t")
    def t(num: int) -> int:
        return 10 // num

    def on_success(_num: int) -> None:
        raise ValueError

    def on_error(_exc: Exception) -> None:
        raise TypeError

    job1 = await t.schedule(1).on_success(on_success).delay(0)
    job2 = await t.schedule(0).on_error(on_error).delay(0)
    with mock.patch("traceback.print_exc") as mock_print_exc:
        await job1.wait()
        await job2.wait()

    total_calls = 3
    mock_print_exc.assert_has_calls([mock.call() for _ in range(total_calls)])


async def test_job_runner_cron_parser_non_empty(
    scheduler: JobScheduler,
    now: datetime,
) -> None:
    @scheduler.register(func_name="t")
    def t(num: int) -> int:
        return 10 // num

    mock_parser = mock.MagicMock()
    mock_parser.next_run.return_value = now
    job_schedule = t.schedule(1)
    job_schedule._cron_parser = mock_parser

    job = await job_schedule.cron("* * * * *", now=now)
    await job.wait()
    assert job_schedule._is_cron is True
