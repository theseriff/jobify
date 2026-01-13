from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import count
from typing import TYPE_CHECKING, Generic, TypeVar
from uuid import uuid4

from jobify._internal.common.constants import INFINITY, JobStatus
from jobify._internal.common.datastructures import RequestState, State
from jobify._internal.configuration import Cron
from jobify._internal.context import JobContext
from jobify._internal.exceptions import DuplicateJobError, JobTimeoutError
from jobify._internal.message import AtArguments, CronArguments, Message
from jobify._internal.scheduler.job import Job
from jobify._internal.scheduler.misfire_policy import handle_misfire_policy
from jobify._internal.storage.abc import ScheduledJob
from jobify._internal.storage.dummy import DummyStorage

if TYPE_CHECKING:
    from jobify._internal.configuration import (
        JobifyConfiguration,
        RouteOptions,
    )
    from jobify._internal.cron_parser import CronParser
    from jobify._internal.inspection import FuncSpec
    from jobify._internal.middleware.base import CallNext
    from jobify._internal.runners import Runnable
    from jobify._internal.shared_state import SharedState


ReturnT = TypeVar("ReturnT")
logger = logging.getLogger("jobify.scheduler")


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
        "_configs",
        "_runnable",
        "_shared_state",
        "_state",
        "func_name",
        "func_spec",
        "route_options",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        shared_state: SharedState,
        jobify_config: JobifyConfiguration,
        runnable: Runnable[ReturnT],
        chain_middleware: CallNext,
        func_name: str,
        func_spec: FuncSpec[ReturnT],
        options: RouteOptions,
    ) -> None:
        self._state: State = state
        self._shared_state: SharedState = shared_state
        self._configs: JobifyConfiguration = jobify_config
        self._runnable: Runnable[ReturnT] = runnable
        self._chain_middleware: CallNext = chain_middleware
        self.func_name: str = func_name
        self.func_spec: FuncSpec[ReturnT] = func_spec
        self.route_options: RouteOptions = options

    def now(self) -> datetime:
        return datetime.now(tz=self._configs.tz)

    def _calculate_delay_seconds(
        self,
        real_now: datetime,
        target_at: datetime,
    ) -> float:
        return target_at.timestamp() - real_now.timestamp()

    def _ensure_job_id(self, job_id: str | None = None) -> str:
        job_id = job_id or uuid4().hex
        if job_id in self._shared_state.pending_jobs:
            raise DuplicateJobError(job_id)
        return job_id

    def _is_persist(self) -> bool:
        return (
            type(self._configs.storage) is not DummyStorage
            and self.route_options.get("durable", True) is True
        )

    def _create_scheduled(
        self,
        trigger: CronArguments | AtArguments,
        job_id: str,
        next_run_at: datetime,
    ) -> ScheduledJob:
        msg = Message(
            job_id=job_id,
            func_name=self.func_name,
            arguments=self._runnable.bound.arguments,
            trigger=trigger,
        )
        for name, arg in msg.arguments.items():
            msg.arguments[name] = self._configs.dumper.dump(
                arg,
                self.func_spec.params_type[name],
            )
        formatted = self._configs.dumper.dump(msg, Message)
        raw_message = self._configs.serializer.dumpb(formatted)
        return ScheduledJob(
            job_id=job_id,
            func_name=self.func_name,
            message=raw_message,
            status=JobStatus.SCHEDULED,
            next_run_at=next_run_at,
        )

    async def _save_scheduled(
        self,
        trigger: CronArguments | AtArguments,
        job_id: str,
        next_run_at: datetime,
    ) -> None:
        scheduled_job = self._create_scheduled(
            trigger,
            job_id,
            next_run_at,
        )
        await self._configs.storage.add_schedule(scheduled_job)

    async def cron(
        self,
        cron: str | Cron,
        *,
        job_id: str,
        now: datetime | None = None,
    ) -> Job[ReturnT]:
        job_id = self._ensure_job_id(job_id)

        real_now = self.now()
        user_now = now or real_now

        if isinstance(cron, str):
            cron = Cron(cron)

        cron_parser = self._configs.cron_factory(cron.expression)
        next_run_at = cron_parser.next_run(now=user_now)

        if self._is_persist():
            trigger = CronArguments(cron=cron, job_id=job_id, offset=user_now)
            await self._save_scheduled(trigger, job_id, next_run_at)

        return self._cron(
            cron=cron,
            job_id=job_id,
            real_now=real_now,
            next_run_at=next_run_at,
            cron_parser=cron_parser,
        )

    def _cron(
        self,
        *,
        cron: Cron,
        job_id: str,
        next_run_at: datetime,
        real_now: datetime,
        cron_parser: CronParser,
    ) -> Job[ReturnT]:
        adjusted_run_at = handle_misfire_policy(
            cron_parser,
            next_run_at,
            real_now,
            cron.misfire_policy,
        )
        job = Job(
            exec_at=adjusted_run_at,
            job_id=job_id,
            pending_jobs=self._shared_state.pending_jobs,
            cron_expression=cron.expression,
            storage=self._configs.storage,
        )
        self._shared_state.pending_jobs[job.id] = job
        cron_ctx = CronContext(job=job, cron=cron, cron_parser=cron_parser)
        delay_seconds = self._calculate_delay_seconds(
            real_now=real_now,
            target_at=adjusted_run_at,
        )
        loop = self._configs.getloop()
        when = loop.time() + delay_seconds
        handle = loop.call_at(when, self._pre_exec_cron, cron_ctx)
        job.bind_handle(handle)
        return job

    async def delay(
        self,
        seconds: float,
        *,
        job_id: str | None = None,
        now: datetime | None = None,
    ) -> Job[ReturnT]:
        job_id = self._ensure_job_id(job_id)

        real_now = self.now()
        now = now or real_now
        at = now + timedelta(seconds=seconds)

        if self._is_persist():
            trigger = AtArguments(at=at, job_id=job_id)
            await self._save_scheduled(trigger, job_id, at)

        return self._at(at=at, job_id=job_id, real_now=real_now)

    async def at(
        self,
        at: datetime,
        *,
        job_id: str | None = None,
    ) -> Job[ReturnT]:
        job_id = self._ensure_job_id(job_id)

        if self._is_persist():
            trigger = AtArguments(at=at, job_id=job_id)
            await self._save_scheduled(trigger, job_id, at)

        return self._at(at=at, job_id=job_id)

    def _at(
        self,
        *,
        at: datetime,
        job_id: str,
        real_now: datetime | None = None,
    ) -> Job[ReturnT]:
        real_now = real_now or self.now()
        job = Job(
            exec_at=at,
            job_id=job_id,
            pending_jobs=self._shared_state.pending_jobs,
            storage=self._configs.storage,
        )
        self._shared_state.pending_jobs[job.id] = job
        loop = self._configs.getloop()
        delay_seconds = self._calculate_delay_seconds(
            real_now=real_now,
            target_at=at,
        )
        if delay_seconds <= 0:
            handle = loop.call_soon(self._pre_exec_at, job)
        else:
            when = loop.time() + delay_seconds
            handle = loop.call_at(when, self._pre_exec_at, job)
        job.bind_handle(handle)
        return job

    def _pre_exec_at(self, job: Job[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_at(job), name=job.id)
        self._shared_state.pending_tasks.add(task)
        event = job._event
        task.add_done_callback(self._shared_state.pending_tasks.discard)
        task.add_done_callback(lambda _: event.set())

    async def _exec_at(self, job: Job[ReturnT]) -> None:
        await self._exec_job(job)
        _ = self._shared_state.pending_jobs.pop(job.id, None)
        if self._is_persist():
            await self._configs.storage.delete_schedule(job.id)

    def _pre_exec_cron(self, ctx: CronContext[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_cron(ctx=ctx), name=ctx.job.id)
        self._shared_state.pending_tasks.add(task)
        event = ctx.job._event
        task.add_done_callback(self._shared_state.pending_tasks.discard)
        task.add_done_callback(lambda _: event.set())

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
            and self._configs.app_started
        ):
            if ctx.is_failure_allowed_by_limit():
                next_run_at = ctx.cron_parser.next_run(now=ctx.job.exec_at)
                if self._is_persist():
                    trigger_with_new_now = CronArguments(
                        cron=ctx.cron,
                        job_id=job.id,
                        offset=job.exec_at,
                    )
                    await self._save_scheduled(
                        trigger_with_new_now,
                        job.id,
                        next_run_at,
                    )
                self._reschedule_cron(ctx, next_run_at)
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

    def _reschedule_cron(
        self,
        ctx: CronContext[ReturnT],
        next_run_at: datetime,
    ) -> None:
        delay_seconds = self._calculate_delay_seconds(
            real_now=self.now(),
            target_at=next_run_at,
        )
        loop = self._configs.getloop()
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._pre_exec_cron, ctx)
        job = ctx.job
        job.update(
            exec_at=next_run_at,
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
            jobify_config=self._configs,
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
