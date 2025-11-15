# ruff: noqa: ANN401
# pyright: reportExplicitAny=false
from typing import Any

from iojobs import Job, JobStatus, State
from iojobs._internal.scheduler import JobScheduler
from iojobs.middleware import BaseMiddleware, CallNextChain


class MyMiddleware(BaseMiddleware):
    def __init__(self, *, skip: bool = False) -> None:
        self.skip: bool = skip

    async def __call__(
        self,
        call_next: CallNextChain[Any],
        job: Job[Any],
        state: State,
    ) -> Any:
        if self.skip is True:
            return None
        return await call_next(job, state)


async def test_middleware(scheduler: JobScheduler) -> None:
    scheduler.middleware.add(MyMiddleware())

    @scheduler.register
    def t1(num: int) -> int:
        return num + 1

    job = await t1.schedule(2).delay(0)
    await job.wait()
    assert job.status is JobStatus.SUCCESS

    scheduler.middleware.add(MyMiddleware(skip=True))
    job = await t1.schedule(2).delay(0)
    await job.wait()
    assert job.status is JobStatus.SKIPPED
