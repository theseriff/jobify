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
from jobber._internal.common.cron_parser import CronParser
from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.context import JobContext
from jobber._internal.exceptions import HandlerSkippedError, NegativeDelayError
from jobber._internal.runner.job import Job

if TYPE_CHECKING:
    from jobber._internal.context import AppContext
    from jobber._internal.middleware.base import CallNext
    from jobber._internal.runner.runnable import Runnable


logger = logging.getLogger("jobber.runner")

_R = TypeVar("_R")


@dataclass(slots=True, kw_only=True, frozen=True)
class ScheduleContext(Generic[_R]):
    job: Job[_R]
    cron_parser: CronParser | None


@final
class ScheduleBuilder(ABC, Generic[_R]):
    __slots__: tuple[str, ...] = (
        "_app_ctx",
        "_job_name",
        "_job_registry",
        "_middleware_chain",
        "_runnable",
        "_state",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        app_ctx: AppContext,
        runnable: Runnable[_R],
        job_name: str,
        job_registry: dict[str, Job[_R]],
        middleware_chain: CallNext,
        state: State,
    ) -> None:
        self._app_ctx = app_ctx
        self._runnable = runnable
        self._job_name = job_name
        self._job_registry = job_registry
        self._middleware_chain = middleware_chain
        self._state: State = state

    async def cron(
        self,
        expression: str,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
    ) -> Job[_R]:
        now = now or datetime.now(tz=self._app_ctx.tz)
        cron_parser = CronParser(expression=expression)
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
    ) -> Job[_R]:
        now = now or datetime.now(tz=self._app_ctx.tz)
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
    ) -> Job[_R]:
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
    ) -> Job[_R]:
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        job = Job(
            exec_at=at,
            job_name=self._job_name,
            job_id=job_id,
            job_registry=self._job_registry,
            job_status=JobStatus.SCHEDULED,
            cron_expression=cron_parser._expression if cron_parser else None,
        )
        ctx = ScheduleContext(job=job, cron_parser=cron_parser)
        loop = self._app_ctx.getloop()
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._schedule_execution, ctx)
        job._timer_handler = time_handler
        self._job_registry[job_id] = job
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

    def _schedule_execution(self, ctx: ScheduleContext[_R]) -> None:
        task = asyncio.create_task(self._exec_job(ctx=ctx))
        self._app_ctx.asyncio_tasks.add(task)
        task.add_done_callback(self._app_ctx.asyncio_tasks.discard)

    async def _exec_job(self, *, ctx: ScheduleContext[_R]) -> None:
        job = ctx.job
        job.status = JobStatus.RUNNING
        job_context = JobContext(
            job=job,
            state=self._state,
            request_state=RequestState(),
            runnable=self._runnable,
        )
        try:
            result = await self._middleware_chain(job_context)
        except HandlerSkippedError:
            logger.debug("Job %s execution was skipped by middleware", job.id)
            job.status = JobStatus.SKIPPED
        except Exception as exc:
            logger.exception("Job %s failed with unexpected error", job.id)
            job.status = JobStatus.FAILED
            job.set_exception(exc)
            raise
        else:
            job.set_result(result)
            job.status = JobStatus.SUCCESS
        finally:
            event = job._event
            if ctx.cron_parser:
                await self._reschedule_cron(ctx)
            else:
                _ = self._job_registry.pop(job.id)
            event.set()

    async def _reschedule_cron(
        self,
        scheduler_ctx: ScheduleContext[_R],
    ) -> None:
        cron_parser = cast("CronParser", scheduler_ctx.cron_parser)
        now = datetime.now(tz=self._app_ctx.tz)
        next_at = cron_parser.next_run(now=now)
        delay_seconds = self._calculate_delay_seconds(now=now, at=next_at)
        loop = self._app_ctx.getloop()
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(
            when,
            self._schedule_execution,
            scheduler_ctx,
        )
        job = scheduler_ctx.job
        job._update(
            exec_at=next_at,
            time_handler=time_handler,
            job_status=JobStatus.SCHEDULED,
        )
