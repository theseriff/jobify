# ruff: noqa: ANN401
# pyright: reportExplicitAny=false
from typing import Any

from jobber import Job, JobStatus, State
from jobber._internal.jobber import Jobber
from jobber.middleware import BaseMiddleware, CallNext


class MyMiddleware(BaseMiddleware):
    def __init__(self, *, skip: bool = False) -> None:
        self.skip: bool = skip

    async def __call__(
        self,
        call_next: CallNext[Any],
        job: Job[Any],
        state: State,
    ) -> Any:
        if self.skip is True:
            return None
        return await call_next(job, state)


async def test_middleware(jobber: Jobber) -> None:
    jobber.middleware.use(MyMiddleware())

    @jobber.register
    def t1(num: int) -> int:
        return num + 1

    job = await t1.schedule(2).delay(0)
    await job.wait()
    assert job.status is JobStatus.SUCCESS

    jobber.middleware.use(MyMiddleware(skip=True))
    job = await t1.schedule(2).delay(0)
    await job.wait()
    assert job.status is JobStatus.SKIPPED
