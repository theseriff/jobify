# pyright: reportPrivateUsage=false
import pytest

from iojobs import JobScheduler
from iojobs._internal.constants import JobStatus
from iojobs._internal.exceptions import JobFailedError


async def test_job(scheduler: JobScheduler) -> None:
    @scheduler.register(job_name="t")
    def t(num: int) -> int:
        return num + 1

    job1 = await t.schedule(1).delay(0)
    job2 = await t.schedule(1).delay(0.01)
    assert str(job1).startswith(f"Job(instance_id={id(job1)}")
    assert str(job2).startswith(f"Job(instance_id={id(job2)}")

    await job1.wait()
    with pytest.warns(RuntimeWarning, match="Job is already done"):
        await job1.wait()

    await job2.cancel()
    assert job2.is_done()
    assert job2.status is JobStatus.CANCELED
    assert job2.id not in job2._job_registered
    assert job2._timer_handler.cancelled()


async def test_job_runner_hooks(scheduler: JobScheduler) -> None:
    expected_on_success = 0
    expected_on_error: Exception = Exception()

    def on_success(num: int) -> None:
        nonlocal expected_on_success
        expected_on_success = num

    def on_error(exc: Exception) -> None:
        nonlocal expected_on_error
        expected_on_error = exc

    @scheduler.register_on_success_hooks(hooks=[on_success])
    @scheduler.register_on_error_hooks(hooks=[on_error])
    @scheduler.register(job_name="t")
    def t(num: int) -> int:
        return 10 // num

    job1 = await t.schedule(1).delay(0)
    job2 = await t.schedule(0).delay(0)
    await job1.wait()
    await job2.wait()

    with pytest.raises(JobFailedError, match="division"):
        assert job2.result()

    assert job1.result() == expected_on_success
    assert isinstance(expected_on_error, ZeroDivisionError)


async def test_job_runner_hooks_fail_usage(scheduler: JobScheduler) -> None:
    def on_success(_num: int) -> None:
        raise ValueError

    def on_error(_exc: Exception) -> None:
        raise TypeError

    @scheduler.register_on_success_hooks(hooks=[on_success])
    @scheduler.register_on_error_hooks(hooks=[on_error])
    @scheduler.register(job_name="t")
    def t(num: int) -> int:
        return 10 // num

    t_reg = scheduler.register(t, job_name="t")
    _ = scheduler.register_on_success_hooks(t_reg, hooks=[on_success])
    _ = scheduler.register_on_error_hooks(t_reg, hooks=[on_error])

    job1 = await t.schedule(1).delay(0)
    job2 = await t.schedule(0).delay(0)

    await job1.wait()
    await job2.wait()

    assert job1.status is JobStatus.SUCCESS
    assert job2.status is JobStatus.FAILED
