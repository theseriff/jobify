# pyright: reportPrivateUsage=false
# ruff: noqa: SLF001
from __future__ import annotations

import asyncio
import logging
from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Generic, TypeVar, cast, final
from uuid import uuid4

from jobber._internal.common.constants import JobStatus
from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.context import JobContext
from jobber._internal.exceptions import (
    JobSkippedError,
    JobTimeoutError,
    NegativeDelayError,
)
from jobber._internal.runner.job import Job

if TYPE_CHECKING:
    from jobber._internal.configuration import (
        JobberConfiguration,
        RouteOptions,
    )
    from jobber._internal.cron_parser import CronParser
    from jobber._internal.middleware.base import CallNext
    from jobber._internal.runner.runners import Runnable


logger = logging.getLogger("jobber.runner")

ReturnT = TypeVar("ReturnT")


@dataclass(slots=True, kw_only=True, frozen=True)
class ScheduleContext(Generic[ReturnT]):
    job: Job[ReturnT]
    cron_parser: CronParser | None


@final
class ScheduleBuilder(ABC, Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "_jobber_config",
        "_middleware_chain",
        "_runnable",
        "_state",
        "func_name",
        "route_options",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        jobber_config: JobberConfiguration,
        runnable: Runnable[ReturnT],
        middleware_chain: CallNext,
        options: RouteOptions,
        func_name: str,
    ) -> None:
        self._state = state
        self._jobber_config = jobber_config
        self._runnable = runnable
        self._middleware_chain = middleware_chain
        self.func_name = func_name
        self.route_options = options

    async def cron(
        self,
        expression: str,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
    ) -> Job[ReturnT]:
        now = now or datetime.now(tz=self._jobber_config.tz)
        cron_parser = self._jobber_config.cron_parser_cls(
            expression=expression
        )
        next_at = cron_parser.next_run(now=now)
        return await self._at(
            now=now,
            at=next_at,
            job_id=job_id or uuid4().hex,
            cron_parser=cron_parser,
        )

    async def delay(
        self,
        delay_seconds: float,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
    ) -> Job[ReturnT]:
        now = now or datetime.now(tz=self._jobber_config.tz)
        at = now + timedelta(seconds=delay_seconds)
        return await self._at(
            now=now,
            at=at,
            job_id=job_id or uuid4().hex,
        )

    async def at(
        self,
        at: datetime,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
    ) -> Job[ReturnT]:
        return await self._at(
            now=now or datetime.now(tz=at.tzinfo),
            at=at,
            job_id=job_id or uuid4().hex,
        )

    async def _at(
        self,
        *,
        now: datetime,
        at: datetime,
        job_id: str,
        cron_parser: CronParser | None = None,
    ) -> Job[ReturnT]:
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        cron_exp = cron_parser.get_expression() if cron_parser else None
        job = Job(
            exec_at=at,
            job_id=job_id,
            func_name=self.func_name,
            job_registry=self._jobber_config._jobs_registry,
            job_status=JobStatus.SCHEDULED,
            cron_expression=cron_exp,
        )
        ctx = ScheduleContext(job=job, cron_parser=cron_parser)
        loop = self._jobber_config.loop_factory()
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._pre_exec_job, ctx)
        job._timer_handler = time_handler
        self._jobber_config._jobs_registry[job.id] = job
        return job

    def _calculate_delay_seconds(
        self,
        now: datetime,
        at: datetime,
    ) -> float:
        now_timestamp = now.timestamp()
        at_timestamp = at.timestamp()
        delay_seconds = at_timestamp - now_timestamp
        if delay_seconds < 0:
            raise NegativeDelayError(delay_seconds)
        return delay_seconds

    def _pre_exec_job(self, ctx: ScheduleContext[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_job(ctx=ctx), name=ctx.job.id)
        self._jobber_config._tasks_registry.add(task)
        task.add_done_callback(self._jobber_config._tasks_registry.discard)

    async def _exec_job(self, *, ctx: ScheduleContext[ReturnT]) -> None:
        job = ctx.job
        job.status = JobStatus.RUNNING
        job_context = JobContext(
            job=job,
            state=self._state,
            request_state=RequestState(),
            runnable=self._runnable,
            route_config=self.route_options,
            jobber_config=self._jobber_config,
        )
        try:
            result = await self._middleware_chain(job_context)
        except JobTimeoutError as exc:
            job.set_exception(exc, status=JobStatus.TIMEOUT)
            job.register_failures()
        except JobSkippedError as exc:
            logger.debug("Job %s execution was skipped by middleware", job.id)
            job.set_exception(exc, status=JobStatus.SKIPPED)
        except Exception as exc:
            logger.exception("Job %s failed with unexpected error", job.id)
            job.set_exception(exc, status=JobStatus.FAILED)
            job.register_failures()
            raise
        else:
            job.set_result(result, status=JobStatus.SUCCESS)
            job.register_success()
        finally:
            job._event.set()
            _ = self._jobber_config._jobs_registry.pop(job.id, None)
            if job.is_cron() and self._jobber_config.app_started:
                max_failures = self.route_options.max_cron_failures
                if job.should_reschedule(max_failures):
                    await self._reschedule_cron(ctx)
                else:
                    logger.warning(
                        "Job %s stopped due to max failures policy (%s/%s)",
                        job.id,
                        job._cron_failures,
                        max_failures,
                    )

    async def _reschedule_cron(
        self,
        scheduler_ctx: ScheduleContext[ReturnT],
    ) -> None:
        cron_parser = cast("CronParser", scheduler_ctx.cron_parser)
        now = datetime.now(tz=self._jobber_config.tz)
        next_at = cron_parser.next_run(now=now)
        delay_seconds = self._calculate_delay_seconds(now=now, at=next_at)
        loop = self._jobber_config.loop_factory()
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._pre_exec_job, scheduler_ctx)
        job = scheduler_ctx.job
        job.update(
            exec_at=next_at,
            time_handler=time_handler,
            job_status=JobStatus.SCHEDULED,
        )
        self._jobber_config._jobs_registry[job.id] = job
