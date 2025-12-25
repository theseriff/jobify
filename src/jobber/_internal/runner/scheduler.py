from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import count
from typing import TYPE_CHECKING, Generic, TypeVar
from uuid import uuid4

from jobber._internal.common.constants import INFINITY, JobStatus
from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.configuration import Cron
from jobber._internal.context import JobContext
from jobber._internal.exceptions import DuplicateJobError, JobTimeoutError
from jobber._internal.message import Message
from jobber._internal.runner.job import Job
from jobber._internal.storage.abc import ScheduledJob
from jobber._internal.storage.dummy import DummyStorage

if TYPE_CHECKING:
    from jobber._internal.configuration import (
        JobberConfiguration,
        RouteOptions,
    )
    from jobber._internal.cron_parser import CronParser
    from jobber._internal.middleware.base import CallNext
    from jobber._internal.runner.runners import Runnable
    from jobber._internal.shared_state import SharedState


logger = logging.getLogger("jobber.runner")


ReturnT = TypeVar("ReturnT")


@dataclass(slots=True, kw_only=True)
class CronContext(Generic[ReturnT]):
    job: Job[ReturnT]
    cron: Cron
    cron_parser: CronParser
    exec_count: count[int] = field(default_factory=lambda: count(start=1))
    failure_count: int = 0

    def is_run_allowed_by_limit(self) -> bool:
        if self.cron.max_runs == INFINITY:
            return True
        return next(self.exec_count) < self.cron.max_runs

    def is_failure_allowed_by_limit(self) -> bool:
        return self.failure_count < self.cron.max_failures


class ScheduleBuilder(Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "_chain_middleware",
        "_jobber_config",
        "_runnable",
        "_shared_state",
        "_state",
        "route_name",
        "route_options",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        shared_state: SharedState,
        jobber_config: JobberConfiguration,
        runnable: Runnable[ReturnT],
        chain_middleware: CallNext,
        route_name: str,
        options: RouteOptions,
    ) -> None:
        self._state: State = state
        self._shared_state: SharedState = shared_state
        self._jobber_config: JobberConfiguration = jobber_config
        self._runnable: Runnable[ReturnT] = runnable
        self._chain_middleware: CallNext = chain_middleware
        self.route_name: str = route_name
        self.route_options: RouteOptions = options

    def _now(self) -> datetime:
        return datetime.now(tz=self._jobber_config.tz)

    def _calculate_delay_seconds(self, now: datetime, at: datetime) -> float:
        return at.timestamp() - now.timestamp()

    def _ensure_job_id(self, job_id: str) -> None:
        if job_id in self._shared_state.pending_jobs:
            raise DuplicateJobError(job_id)

    def _should_persist(self) -> bool:
        return (
            not isinstance(self._jobber_config.storage, DummyStorage)
            and self.route_options.get("durable", True) is True
        )

    async def cron(
        self,
        cron: str | Cron,
        *,
        job_id: str,
        now: datetime | None = None,
    ) -> Job[ReturnT]:
        self._ensure_job_id(job_id)
        now = now or self._now()

        if isinstance(cron, str):
            cron = Cron(cron)

        cron_parser = self._jobber_config.cron_factory(cron.expression)
        at = cron_parser.next_run(now=now)

        job = Job(
            exec_at=at,
            job_id=job_id,
            pending_jobs=self._shared_state.pending_jobs,
            cron_expression=cron.expression,
            storage=self._jobber_config.storage,
        )
        cron_ctx = CronContext(job=job, cron=cron, cron_parser=cron_parser)
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        loop = self._jobber_config.getloop()
        when = loop.time() + delay_seconds
        handle = loop.call_at(when, self._pre_exec_cron, cron_ctx)
        job.bind_handle(handle)
        self._shared_state.pending_jobs[job.id] = job

        if self._should_persist():
            message = Message(
                job_id=job_id,
                route_name=self.route_name,
                arguments=self._runnable.bound.arguments,
                cron={"cron": cron, "job_id": job_id, "now": now},
            )
            await self._save_scheduled(message, job.status)

        return job

    async def delay(
        self,
        seconds: float,
        *,
        job_id: str | None = None,
        now: datetime | None = None,
    ) -> Job[ReturnT]:
        now = now or self._now()
        at = now + timedelta(seconds=seconds)
        return await self._at(at=at, now=now, job_id=job_id)

    async def at(
        self,
        at: datetime,
        *,
        job_id: str | None = None,
        now: datetime | None = None,
    ) -> Job[ReturnT]:
        return await self._at(
            at=at,
            now=now or datetime.now(tz=at.tzinfo),
            job_id=job_id,
        )

    async def _at(
        self,
        *,
        at: datetime,
        now: datetime,
        job_id: str | None,
    ) -> Job[ReturnT]:
        job_id = job_id or uuid4().hex
        self._ensure_job_id(job_id)

        job = Job(
            exec_at=at,
            job_id=job_id,
            pending_jobs=self._shared_state.pending_jobs,
            storage=self._jobber_config.storage,
        )
        self._shared_state.pending_jobs[job.id] = job

        loop = self._jobber_config.getloop()
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        if delay_seconds <= 0:
            handle = loop.call_soon(self._pre_exec_at_without_persist, job)
            job.bind_handle(handle)
            return job

        when = loop.time() + delay_seconds
        if self._should_persist():
            handle = loop.call_at(when, self._pre_exec_at, job)
            message = Message(
                job_id=job_id,
                route_name=self.route_name,
                arguments=self._runnable.bound.arguments,
                at={"at": at, "job_id": job_id, "now": now},
            )
            await self._save_scheduled(message, job.status)

        else:
            handle = loop.call_at(when, self._pre_exec_at_without_persist, job)

        job.bind_handle(handle)
        return job

    async def _save_scheduled(self, msg: Message, status: JobStatus) -> None:
        formatted = self._jobber_config.dumper.dump(msg, Message)
        raw_message = self._jobber_config.serializer.dumpb(formatted)
        scheduled_job = ScheduledJob(
            job_id=msg.job_id,
            route_name=self.route_name,
            message=raw_message,
            status=status,
        )
        await self._jobber_config.storage.add_schedule(scheduled_job)

    def _pre_exec_at_without_persist(self, job: Job[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_at(job), name=job.id)
        self._shared_state.pending_tasks.add(task)
        task.add_done_callback(self._shared_state.pending_tasks.discard)

    async def _exec_at_without_persist(self, job: Job[ReturnT]) -> None:
        await self._exec_job(job)
        _ = self._shared_state.pending_jobs.pop(job.id, None)

    def _pre_exec_at(self, job: Job[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_at(job), name=job.id)
        self._shared_state.pending_tasks.add(task)
        task.add_done_callback(self._shared_state.pending_tasks.discard)

    async def _exec_at(self, job: Job[ReturnT]) -> None:
        await self._exec_job(job)
        _ = self._shared_state.pending_jobs.pop(job.id, None)
        if self._should_persist():
            await self._jobber_config.storage.delete_schedule(job_id=job.id)

    def _pre_exec_cron(self, ctx: CronContext[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_cron(ctx=ctx), name=ctx.job.id)
        self._shared_state.pending_tasks.add(task)
        task.add_done_callback(self._shared_state.pending_tasks.discard)

    async def _exec_cron(self, ctx: CronContext[ReturnT]) -> None:
        job = ctx.job
        await self._exec_job(job)
        if job.status is JobStatus.SUCCESS:
            ctx.failure_count = 0
        else:
            ctx.failure_count += 1
        if (
            job.is_reschedulable()
            and ctx.is_run_allowed_by_limit()
            and self._jobber_config.app_started
        ):
            if ctx.is_failure_allowed_by_limit():
                self._reschedule_cron(ctx)
            else:
                job._status = JobStatus.PERMANENTLY_FAILED
                logger.warning(
                    "Job %s stopped due to max failures policy (%s/%s)",
                    job.id,
                    ctx.failure_count,
                    ctx.cron.max_failures,
                )
                _ = self._shared_state.pending_jobs.pop(job.id, None)
        else:
            _ = self._shared_state.pending_jobs.pop(job.id, None)

    def _reschedule_cron(self, ctx: CronContext[ReturnT]) -> None:
        now = self._now()
        next_at = ctx.cron_parser.next_run(now=now)
        delay_seconds = self._calculate_delay_seconds(now=now, at=next_at)
        loop = self._jobber_config.getloop()
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._pre_exec_cron, ctx)
        job = ctx.job
        job.update(
            exec_at=next_at,
            time_handler=time_handler,
            job_status=JobStatus.SCHEDULED,
        )

    async def _exec_job(self, job: Job[ReturnT]) -> None:
        job._status = JobStatus.RUNNING
        job_context = JobContext(
            job=job,
            state=self._state,
            request_state=RequestState(),
            runnable=self._runnable,
            route_options=self.route_options,
            jobber_config=self._jobber_config,
        )
        try:
            result = await self._chain_middleware(job_context)
        except JobTimeoutError as exc:
            job.set_exception(exc, status=JobStatus.TIMEOUT)
        except Exception as exc:
            logger.exception("Job %s failed with unexpected error", job.id)
            job.set_exception(exc, status=JobStatus.FAILED)
        else:
            job.set_result(result, status=JobStatus.SUCCESS)
        finally:
            job._event.set()
