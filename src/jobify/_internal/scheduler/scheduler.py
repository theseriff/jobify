from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Generic, TypeVar, cast
from uuid import uuid4

from jobify._internal.common.constants import JobStatus
from jobify._internal.common.datastructures import RequestState, State
from jobify._internal.configuration import Cron
from jobify._internal.context import JobContext, OuterContext
from jobify._internal.exceptions import DuplicateJobError, JobTimeoutError
from jobify._internal.message import AtArguments, CronArguments, Message
from jobify._internal.scheduler.job import CronContext, Job
from jobify._internal.scheduler.misfire_policy import handle_misfire_policy
from jobify._internal.storage.abc import ScheduledJob
from jobify._internal.storage.dummy import DummyStorage

if TYPE_CHECKING:
    from collections.abc import Callable

    from jobify._internal.configuration import (
        JobifyConfiguration,
        RouteOptions,
    )
    from jobify._internal.cron_parser import CronParser
    from jobify._internal.inspection import FuncSpec
    from jobify._internal.middleware.base import CallNext, CallNextOuter
    from jobify._internal.runners import Runnable
    from jobify._internal.shared_state import SharedState

WARN_FORCE = (
    "Job {job_id} already scheduled for {schedule}. If you need to "
    "reschedule, cancel the existing job first or use force=True."
)
ReturnT = TypeVar("ReturnT")
logger = logging.getLogger("jobify.scheduler")


class ScheduleBuilder(Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "_chain_middleware",
        "_chain_outer_middleware",
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
        chain_outer_middleware: CallNextOuter,
        func_spec: FuncSpec[ReturnT],
        options: RouteOptions,
        name: str,
    ) -> None:
        self._state: State = state
        self._shared_state: SharedState = shared_state
        self._configs: JobifyConfiguration = jobify_config
        self._runnable: Runnable[ReturnT] = runnable
        self._chain_middleware: CallNext = chain_middleware
        self._chain_outer_middleware: CallNextOuter = chain_outer_middleware
        self.func_spec: FuncSpec[ReturnT] = func_spec
        self.route_options: RouteOptions = options
        self.name: str = name

    def now(self) -> datetime:
        return datetime.now(tz=self._configs.tz)

    def _calculate_delay_seconds(self, target_at: datetime) -> float:
        return target_at.timestamp() - self.now().timestamp()

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
            self._create_scheduled_job(job_id, next_run_at, trigger)
        )

    def _create_scheduled_job(
        self,
        job_id: str,
        next_run_at: datetime,
        trigger: CronArguments | AtArguments,
    ) -> ScheduledJob:
        dumper = self._configs.dumper.dump
        params_type = self.func_spec.params_type
        args_dumped = {
            name: dumper(arg, params_type[name])
            for name, arg in self._runnable.bound.arguments.items()
        }
        msg = Message(
            job_id=job_id,
            name=self.name,
            arguments=args_dumped,
            trigger=trigger,
        )
        serializer = self._configs.serializer.dumpb
        serialized_message = serializer(dumper(msg, Message))
        return ScheduledJob(
            name=self.name,
            job_id=job_id,
            message=serialized_message,
            status=JobStatus.SCHEDULED,
            next_run_at=next_run_at,
        )

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

    def _create_outer_context(
        self,
        *,
        job: Job[ReturnT],
        trigger: AtArguments | CronArguments,
        is_force: bool,
        is_replace: bool,
        schedule_hook: Callable[[], asyncio.Handle],
    ) -> OuterContext:
        return OuterContext(
            job=job,
            state=self._state,
            trigger=trigger,
            runnable=self._runnable,
            arguments=self._runnable.bound.arguments,
            func_spec=self.func_spec,
            is_force=is_force,
            is_persist=self._is_persist(),
            is_replace=is_replace,
            route_options=self.route_options,
            jobify_config=self._configs,
            request_state=RequestState(),
            persist_job_hook=self._persist_job,
            schedule_hook=schedule_hook,
        )

    async def cron(
        self,
        cron: str | Cron,
        *,
        job_id: str,
        replace: bool = False,
        force: bool = False,
    ) -> Job[ReturnT]:
        job_id, exists_job = self._ensure_job_id(job_id, replace=replace)
        if isinstance(cron, str):
            cron = Cron(cron)

        real_now = self.now()

        if exists_job is not None:
            job = exists_job
            ctx = cast("CronContext[ReturnT]", exists_job._cron_context)

            if not force and cron == ctx.cron:
                logger.warning(WARN_FORCE.format(job_id=job_id, schedule=cron))
                return exists_job

            old_cron = ctx.cron
            current_offset = ctx.offset
        else:
            job = Job[ReturnT](
                exec_at=real_now,
                job_id=job_id,
                unregister_hook=self._shared_state.unregister_job,
                storage=self._configs.storage,
            )
            ctx = None
            old_cron = None
            current_offset = real_now

        parser = self._configs.cron_factory(cron.expression)
        offset, next_run_at = self._calculate_schedule_cron(
            old_cron=old_cron,
            new_cron=cron,
            parser=parser,
            offset=current_offset,
            real_now=real_now,
        )
        job.exec_at = next_run_at
        if ctx is not None:
            ctx.cron = cron
            ctx.offset = offset
            ctx.run_count = 0
            ctx.cron_parser = parser
        else:
            ctx = CronContext(
                job=job,
                cron=cron,
                offset=offset,
                run_count=0,
                cron_parser=parser,
            )
            job.bind_cron_context(ctx)
        _ = await self._chain_outer_middleware(
            self._create_outer_context(
                job=job,
                trigger=CronArguments(cron=cron, job_id=job_id, offset=offset),
                is_force=force,
                is_replace=replace,
                schedule_hook=lambda: self._schedule_execution_cron(ctx),
            )
        )
        return job

    def _calculate_schedule_cron(
        self,
        *,
        old_cron: Cron | None,
        new_cron: Cron,
        parser: CronParser,
        offset: datetime,
        real_now: datetime,
    ) -> tuple[datetime, datetime]:
        start_date_changed = old_cron is None or (
            old_cron.start_date != new_cron.start_date
        )
        if start_date_changed and new_cron.start_date is not None:
            target_at = new_cron.start_date
            offset = target_at
        else:
            target_at = parser.next_run(now=offset)

        next_run_at = handle_misfire_policy(
            cron_parser=parser,
            next_run_at=target_at,
            real_now=real_now,
            policy=new_cron.misfire_policy,
        )
        return (offset, next_run_at)

    def _schedule_execution_cron(
        self,
        ctx: CronContext[ReturnT],
    ) -> asyncio.Handle:
        delay_seconds = self._calculate_delay_seconds(ctx.job.exec_at)
        loop = self._configs.getloop()
        when = loop.time() + delay_seconds
        handle = loop.call_at(when, self._pre_exec_cron, ctx)
        ctx.job.bind_handle(handle)
        return handle

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
        force: bool = False,
    ) -> Job[ReturnT]:
        job_id, exists_job = self._ensure_job_id(job_id, replace=replace)
        if exists_job is not None:
            if not force and exists_job.exec_at == at:
                logger.warning(WARN_FORCE.format(job_id=job_id, schedule=at))
                return exists_job
            exists_job.exec_at = at
            job = exists_job
        else:
            job = Job[ReturnT](
                exec_at=at,
                job_id=job_id,
                storage=self._configs.storage,
                unregister_hook=self._shared_state.unregister_job,
            )
        _ = await self._chain_outer_middleware(
            self._create_outer_context(
                job=job,
                trigger=AtArguments(at, job_id),
                is_force=force,
                is_replace=replace,
                schedule_hook=lambda: self._schedule_execution_at(job),
            )
        )
        return job

    def _schedule_execution_at(self, job: Job[ReturnT]) -> asyncio.Handle:
        loop = self._configs.getloop()
        delay_seconds = self._calculate_delay_seconds(target_at=job.exec_at)
        if delay_seconds <= 0:
            handle = loop.call_soon(self._pre_exec_at, job)
        else:
            when = loop.time() + delay_seconds
            handle = loop.call_at(when, self._pre_exec_at, job)
        job.bind_handle(handle)
        return handle

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
        ctx.run_count += 1

        if ctx.is_run_exceeded_by_limit():
            if self._is_persist():
                await self._configs.storage.delete_schedule(job.id)
        elif job.is_reschedulable() and self._configs.app_started:
            if ctx.is_failure_allowed_by_limit():
                offset = ctx.offset = job.exec_at
                next_run_at = ctx.cron_parser.next_run(now=offset)

                if self._is_persist():
                    trigger = CronArguments(
                        ctx.cron,
                        job.id,
                        offset,
                        ctx.run_count,
                    )
                    await self._persist_job(job.id, next_run_at, trigger)
                job.update(exec_at=next_run_at, status=JobStatus.SCHEDULED)
                _ = self._schedule_execution_cron(ctx)
                return

            job._status = JobStatus.PERMANENTLY_FAILED
            logger.warning(
                "Job %s stopped due to max failures policy (%s/%s)",
                job.id,
                ctx.failure_count,
                ctx.cron.max_failures,
            )
        self._shared_state.unregister_job(job.id)

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

    def _cron(  # noqa: PLR0913
        self,
        *,
        cron: Cron,
        job_id: str,
        offset: datetime,
        next_run_at: datetime,
        cron_parser: CronParser,
        run_count: int,
    ) -> None:
        job = Job[ReturnT](
            exec_at=next_run_at,
            job_id=job_id,
            unregister_hook=self._shared_state.unregister_job,
            storage=self._configs.storage,
        )
        ctx = CronContext(
            job=job,
            cron=cron,
            offset=offset,
            cron_parser=cron_parser,
            run_count=run_count,
        )
        job.bind_cron_context(ctx)
        self._shared_state.register_job(job)
        _ = self._schedule_execution_cron(ctx)

    def _at(self, at: datetime, job_id: str) -> None:
        job = Job[ReturnT](
            exec_at=at,
            job_id=job_id,
            unregister_hook=self._shared_state.unregister_job,
            storage=self._configs.storage,
        )
        self._shared_state.register_job(job)
        _ = self._schedule_execution_at(job)
