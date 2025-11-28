# pyright: reportPrivateUsage=false

from jobber import Jobber
from jobber._internal.common.constants import JobStatus


async def test_job() -> None:
    jobber = Jobber()

    @jobber.register(job_name="t")
    def t(num: int) -> int:
        return num + 1

    async with jobber:
        job1 = await t.schedule(1).delay(0)
        job2 = await t.schedule(1).delay(0.01)
        assert str(job1).startswith(f"Job(instance_id={id(job1)}")
        assert str(job2).startswith(f"Job(instance_id={id(job2)}")

    await job1.wait()
    await job2.cancel()

    assert job2.is_done()
    assert job2.status is JobStatus.CANCELED
    assert job2.id not in job2._job_registry
    assert job2._timer_handler.cancelled()
