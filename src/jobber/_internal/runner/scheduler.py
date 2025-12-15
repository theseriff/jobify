from __future__ import annotations

import asyncio
import itertools
import logging
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Generic, TypeVar, cast, final
from uuid import uuid4

from jobber._internal.common.constants import INFINITY, JobStatus
from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.configuration import Cron
from jobber._internal.context import JobContext
from jobber._internal.exceptions import (
    DuplicateJobError,
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


@dataclass(slots=True, kw_only=True)
class CronContext:
    cron: Cron
    cron_parser: CronParser
    exec_count: itertools.count[int] = field(default_factory=itertools.count)

    def is_run_allowed_by_limit(self) -> bool:
        if self.cron.max_runs is INFINITY:
            return True
        return next(self.exec_count) < self.cron.max_runs


@dataclass(slots=True, kw_only=True, frozen=True)
class ScheduleContext(Generic[ReturnT]):
    job: Job[ReturnT]
    cron_ctx: CronContext | None


@final
class ScheduleBuilder(ABC, Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "_chain_middleware",
        "_jobber_config",
        "_runnable",
        "_state",
        "name",
        "route_options",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        jobber_config: JobberConfiguration,
        runnable: Runnable[ReturnT],
        chain_middleware: CallNext,
        options: RouteOptions,
        name: str,
    ) -> None:
        self._state = state
        self._jobber_config = jobber_config
        self._runnable = runnable
        self._chain_middleware = chain_middleware
        self.name = name
        self.route_options = options

    def _now(self) -> datetime:
        return datetime.now(tz=self._jobber_config.tz)

    async def cron(
        self,
        cron: str | Cron,
        /,
        *,
        job_id: str,
        now: datetime | None = None,
    ) -> Job[ReturnT]:
        now = now or self._now()
        if isinstance(cron, str):
            cron = Cron(cron)

        cron_parser = self._jobber_config.factory_cron(cron.expression)
        next_at = cron_parser.next_run(now=now)

        return await self._at(
            now=now,
            at=next_at,
            job_id=job_id or uuid4().hex,
            cron_ctx=CronContext(cron=cron, cron_parser=cron_parser),
        )

    async def delay(
        self,
        delay_seconds: float,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
    ) -> Job[ReturnT]:
        now = now or self._now()
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
        cron_ctx: CronContext | None = None,
    ) -> Job[ReturnT]:
        if job_id in self._jobber_config._jobs_registry:
            raise DuplicateJobError(job_id)
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        job = Job(
            exec_at=at,
            job_id=job_id,
            name=self.name,
            job_registry=self._jobber_config._jobs_registry,
            job_status=JobStatus.SCHEDULED,
            cron_expression=cron_ctx.cron.expression if cron_ctx else None,
        )
        ctx = ScheduleContext(job=job, cron_ctx=cron_ctx)
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
        job._status = JobStatus.RUNNING
        job_context = JobContext(
            job=job,
            state=self._state,
            request_state=RequestState(),
            runnable=self._runnable,
            route_config=self.route_options,
            jobber_config=self._jobber_config,
        )
        shutdown_graceful = False
        try:
            result = await self._chain_middleware(job_context)
        except asyncio.CancelledError:
            shutdown_graceful = True
            raise
        except JobTimeoutError as exc:
            job.set_exception(exc, status=JobStatus.TIMEOUT)
            job.register_failures()
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
            if (
                ctx.cron_ctx
                and ctx.cron_ctx.is_run_allowed_by_limit()
                and job.is_reschedulable()
                and not shutdown_graceful
                and self._jobber_config.app_started
            ):
                max_failures = ctx.cron_ctx.cron.max_failures
                if job._cron_failures < max_failures:
                    self._reschedule_cron(ctx)
                else:
                    job._status = JobStatus.PERMANENTLY_FAILED
                    logger.warning(
                        "Job %s stopped due to max failures policy (%s/%s)",
                        job.id,
                        job._cron_failures,
                        max_failures,
                    )
                    _ = self._jobber_config._jobs_registry.pop(job.id, None)

            else:
                _ = self._jobber_config._jobs_registry.pop(job.id, None)

    def _reschedule_cron(
        self,
        scheduler_ctx: ScheduleContext[ReturnT],
    ) -> None:
        cron_ctx = cast("CronContext", scheduler_ctx.cron_ctx)
        now = self._now()
        next_at = cron_ctx.cron_parser.next_run(now=now)
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
