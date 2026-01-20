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
    from jobify._internal.serializers.base import JSONCompat
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
        "func_spec",
        "name",
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
        func_spec: FuncSpec[ReturnT],
        options: RouteOptions,
        name: str,
    ) -> None:
        self._state: State = state
        self._shared_state: SharedState = shared_state
        self._configs: JobifyConfiguration = jobify_config
        self._runnable: Runnable[ReturnT] = runnable
        self._chain_middleware: CallNext = chain_middleware
        self.func_spec: FuncSpec[ReturnT] = func_spec
        self.route_options: RouteOptions = options
        self.name: str = name

    def now(self) -> datetime:
        return datetime.now(tz=self._configs.tz)

    def _calculate_delay_seconds(self, target_at: datetime) -> float:
        return target_at.timestamp() - self.now().timestamp()

    def _ensure_job_id(
        self,
        job_id: str | None,
        *,
        replace: bool,
    ) -> tuple[str, Job[ReturnT] | None]:
        job_id = job_id or uuid4().hex
        if job := self._shared_state.pending_jobs.get(job_id):
            if replace is True:
                return (job_id, job)
            raise DuplicateJobError(job_id)
        return (job_id, None)

    def _is_persist(self) -> bool:
        is_dummy = isinstance(self._configs.storage, DummyStorage)
        is_durable = self.route_options.get("durable", True)
        return not is_dummy and is_durable

    async def _persist_job(
        self,
        job_id: str,
        next_run_at: datetime,
        trigger: CronArguments | AtArguments,
    ) -> None:
        await self._configs.storage.add_schedule(
            ScheduledJob.create(
                job_id,
                self.name,
                self._serialize_job_message(trigger),
                next_run_at,
            )
        )

    def _serialize_job_message(
        self,
        trigger: CronArguments | AtArguments,
    ) -> bytes:
        raw_args = self._runnable.origin_arguments
        params_type = self.func_spec.params_type
        dumper_hook = self._configs.dumper.dump
        dumped_args: dict[str, JSONCompat] = {
            name: dumper_hook(arg_val, params_type[name])
            for name, arg_val in raw_args.items()
        }
        msg = Message(
            job_id=trigger.job_id,
            name=self.name,
            arguments=dumped_args,
            trigger=trigger,
        )
        formatted_msg = self._configs.dumper.dump(msg, Message)
        return self._configs.serializer.dumpb(formatted_msg)

    async def cron(
        self,
        cron: str | Cron,
        *,
        job_id: str,
        now: datetime | None = None,
        replace: bool = False,
    ) -> Job[ReturnT]:
        job_id, exists_job = self._ensure_job_id(job_id, replace=replace)

        real_now = self.now()
        offset = now or real_now

        if exists_job is not None:
            exists_job._cancel()
            offset = now or exists_job._offset or offset

        if isinstance(cron, str):
            cron = Cron(cron)

        cron_parser = self._configs.cron_factory(cron.expression)
        next_run_at = handle_misfire_policy(
            cron_parser,
            cron_parser.next_run(now=offset),
            real_now,
            cron.misfire_policy,
        )
        if self._is_persist():
            trigger = CronArguments(cron=cron, job_id=job_id, offset=offset)
            await self._persist_job(job_id, next_run_at, trigger)

        return self._cron(
            cron=cron,
            job_id=job_id,
            offset=offset,
            next_run_at=next_run_at,
            cron_parser=cron_parser,
        )

    def _cron(
        self,
        *,
        cron: Cron,
        job_id: str,
        offset: datetime,
        next_run_at: datetime,
        cron_parser: CronParser,
    ) -> Job[ReturnT]:
        job = Job[ReturnT](
            exec_at=next_run_at,
            job_id=job_id,
            unregister_hook=self._shared_state.unregister_job,
            storage=self._configs.storage,
            cron_expression=cron.expression,
            offset=offset,
        )
        self._shared_state.register_job(job)
        cron_ctx = CronContext(job=job, cron=cron, cron_parser=cron_parser)
        delay_seconds = self._calculate_delay_seconds(target_at=next_run_at)
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
        replace: bool = False,
    ) -> Job[ReturnT]:
        now = now or self.now()
        at = now + timedelta(seconds=seconds)
        return await self.at(at=at, job_id=job_id, replace=replace)

    async def at(
        self,
        at: datetime,
        *,
        job_id: str | None = None,
        replace: bool = False,
    ) -> Job[ReturnT]:
        job_id, exists_job = self._ensure_job_id(job_id, replace=replace)
        if exists_job is not None:
            exists_job._cancel()

        if self._is_persist():
            trigger = AtArguments(at=at, job_id=job_id)
            await self._persist_job(job_id, at, trigger)

        return self._at(at=at, job_id=job_id)

    def _at(
        self,
        *,
        at: datetime,
        job_id: str,
    ) -> Job[ReturnT]:
        job = Job[ReturnT](
            exec_at=at,
            job_id=job_id,
            unregister_hook=self._shared_state.unregister_job,
            storage=self._configs.storage,
        )
        self._shared_state.register_job(job)
        loop = self._configs.getloop()
        delay_seconds = self._calculate_delay_seconds(target_at=at)
        if delay_seconds <= 0:
            handle = loop.call_soon(self._pre_exec_at, job)
        else:
            when = loop.time() + delay_seconds
            handle = loop.call_at(when, self._pre_exec_at, job)
        job.bind_handle(handle)
        return job

    def _pre_exec_at(self, job: Job[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_at(job), name=job.id)
        self._shared_state.track_task(task, job._event)

    async def _exec_at(self, job: Job[ReturnT]) -> None:
        await self._exec_job(job)
        self._shared_state.unregister_job(job.id)
        if self._is_persist():
            await self._configs.storage.delete_schedule(job.id)

    def _pre_exec_cron(self, ctx: CronContext[ReturnT]) -> None:
        task = asyncio.create_task(self._exec_cron(ctx=ctx), name=ctx.job.id)
        self._shared_state.track_task(task, ctx.job._event)

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
                offset = job._offset = job.exec_at
                next_run_at = ctx.cron_parser.next_run(now=offset)
                if self._is_persist():
                    trigger = CronArguments(ctx.cron, job.id, offset)
                    await self._persist_job(job.id, next_run_at, trigger)
                self._reschedule_cron(ctx, next_run_at)
            else:
                job._status = JobStatus.PERMANENTLY_FAILED
                logger.warning(
                    "Job %s stopped due to max failures policy (%s/%s)",
                    job.id,
                    ctx.failure_count,
                    ctx.cron.max_failures,
                )
                self._shared_state.unregister_job(job.id)
        else:
            self._shared_state.unregister_job(job.id)

    def _reschedule_cron(
        self,
        ctx: CronContext[ReturnT],
        next_run_at: datetime,
    ) -> None:
        delay_seconds = self._calculate_delay_seconds(target_at=next_run_at)
        loop = self._configs.getloop()
        when = loop.time() + delay_seconds
        handle = loop.call_at(when, self._pre_exec_cron, ctx)
        job = ctx.job
        job.update(
            exec_at=next_run_at,
            time_handler=handle,
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
