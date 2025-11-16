# pyright: reportPrivateUsage=false
# ruff: noqa: SLF001
from __future__ import annotations

import asyncio
import logging
import traceback
from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Generic, ParamSpec, TypeVar, cast
from uuid import uuid4

from jobber._internal.common.constants import EMPTY, ExecutionMode, JobStatus
from jobber._internal.common.cron_parser import CronParser
from jobber._internal.common.datastructures import State
from jobber._internal.exceptions import HandlerSkippedError, NegativeDelayError
from jobber._internal.runner.executor import Executor, create_executor
from jobber._internal.runner.job import Job

if TYPE_CHECKING:
    from collections.abc import Callable

    from jobber._internal.common.annotations import AnyDict
    from jobber._internal.context import JobberContext
    from jobber._internal.handler import Handler
    from jobber._internal.middleware.pipeline import MiddlewarePipeline


logger = logging.getLogger("jobber.runner")

_ReturnType = TypeVar("_ReturnType")
_FuncParams = ParamSpec("_FuncParams")


@dataclass(slots=True, kw_only=True)
class ExecutionContext(Generic[_ReturnType]):
    job: Job[_ReturnType]
    executor: Executor[_ReturnType]
    cron_parser: CronParser | None
    execution_mode: ExecutionMode


class JobScheduler(ABC, Generic[_FuncParams, _ReturnType]):
    __slots__: tuple[str, ...] = (
        "_cron_parser",
        "_extra",
        "_handler",
        "_job_registry",
        "_jobber_ctx",
        "_middleware",
        "_on_error_hooks",
        "_on_success_hooks",
        "_state",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        handler: Handler[_FuncParams, _ReturnType],
        jobber_ctx: JobberContext,
        job_registry: dict[str, Job[_ReturnType]],
        on_success_hooks: list[Callable[[_ReturnType], None]],
        on_error_hooks: list[Callable[[Exception], None]],
        middleware: MiddlewarePipeline,
        extra: AnyDict,
    ) -> None:
        self._state: State = state
        self._handler: Handler[_FuncParams, _ReturnType] = handler
        self._jobber_ctx: JobberContext = jobber_ctx
        self._on_success_hooks: list[Callable[[_ReturnType], None]] = (
            on_success_hooks
        )
        self._on_error_hooks: list[Callable[[Exception], None]] = (
            on_error_hooks
        )
        self._job_registry: Final = job_registry
        self._cron_parser: CronParser = EMPTY
        self._middleware: MiddlewarePipeline = middleware
        self._extra: AnyDict = extra

    async def cron(
        self,
        expression: str,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
        execution_mode: ExecutionMode = ExecutionMode.MAIN,
    ) -> Job[_ReturnType]:
        now = now or datetime.now(tz=self._jobber_ctx.tz)
        cron_parser = CronParser(expression=expression)
        next_at = cron_parser.next_run(now=now)
        return await self._at(
            now=now,
            at=next_at,
            job_id=job_id or uuid4().hex,
            exec_mode=execution_mode,
            cron_parser=cron_parser,
        )

    async def delay(
        self,
        delay_seconds: float,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
        execution_mode: ExecutionMode = ExecutionMode.MAIN,
    ) -> Job[_ReturnType]:
        now = now or datetime.now(tz=self._jobber_ctx.tz)
        at = now + timedelta(seconds=delay_seconds)
        return await self._at(
            now=now,
            at=at,
            job_id=job_id or uuid4().hex,
            exec_mode=execution_mode,
        )

    async def at(
        self,
        at: datetime,
        /,
        *,
        now: datetime | None = None,
        job_id: str | None = None,
        execution_mode: ExecutionMode = ExecutionMode.MAIN,
    ) -> Job[_ReturnType]:
        return await self._at(
            now=now or datetime.now(tz=at.tzinfo),
            at=at,
            job_id=job_id or uuid4().hex,
            exec_mode=execution_mode,
        )

    async def _at(
        self,
        *,
        now: datetime,
        at: datetime,
        job_id: str,
        exec_mode: ExecutionMode,
        cron_parser: CronParser | None = None,
    ) -> Job[_ReturnType]:
        self._handler.job_id = job_id
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        executor = create_executor(self._handler, exec_mode, self._jobber_ctx)
        job = Job(
            exec_at=at,
            job_name=self._handler.job_name,
            job_id=job_id,
            job_registry=self._job_registry,
            job_status=JobStatus.SCHEDULED,
            cron_expression=cron_parser._expression if cron_parser else None,
        )
        runner_ctx = ExecutionContext(
            job=job,
            executor=executor,
            cron_parser=cron_parser,
            execution_mode=exec_mode,
        )
        loop = self._jobber_ctx.loop
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._schedule_execution, runner_ctx)
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

    def _schedule_execution(self, ctx: ExecutionContext[_ReturnType]) -> None:
        task = asyncio.create_task(self._exec_job(ctx=ctx))
        self._jobber_ctx.asyncio_tasks.add(task)
        task.add_done_callback(self._jobber_ctx.asyncio_tasks.discard)

    async def _exec_job(self, *, ctx: ExecutionContext[_ReturnType]) -> None:
        job = ctx.job
        job.status = JobStatus.RUNNING
        self._state.request = State()
        middleware_chain = self._middleware.compose(
            ctx.executor.run,
            raise_if_skipped=True,
        )
        try:
            result = await middleware_chain(job, self._state)
        except HandlerSkippedError:
            logger.debug("Job %s execution was skipped by middleware", job.id)
            job.status = JobStatus.SKIPPED
        except Exception as exc:
            logger.exception("Job %s failed with unexpected error", job.id)
            job.status = JobStatus.FAILED
            job.set_exception(exc)
            self._run_hooks_error(exc)
        else:
            job.set_result(result)
            job.status = JobStatus.SUCCESS
            self._run_hooks_success(result)
        finally:
            event = job._event
            if ctx.cron_parser:
                await self._reschedule_cron(ctx)
            else:
                _ = self._job_registry.pop(job.id)
            event.set()

    async def _reschedule_cron(
        self,
        runner_ctx: ExecutionContext[_ReturnType],
    ) -> None:
        cron_parser = cast("CronParser", runner_ctx.cron_parser)
        now = datetime.now(tz=self._jobber_ctx.tz)
        next_at = cron_parser.next_run(now=now)
        delay_seconds = self._calculate_delay_seconds(now=now, at=next_at)
        loop = self._jobber_ctx.loop
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._schedule_execution, runner_ctx)
        job = runner_ctx.job
        job._update(
            exec_at=next_at,
            time_handler=time_handler,
            job_status=JobStatus.SCHEDULED,
        )

    def _run_hooks_success(self, result: _ReturnType) -> None:
        for call_success in self._on_success_hooks:
            try:
                call_success(result)
            except Exception:  # noqa: BLE001, PERF203
                traceback.print_exc()

    def _run_hooks_error(self, exc: Exception) -> None:
        for call_error in self._on_error_hooks:
            try:
                call_error(exc)
            except Exception:  # noqa: BLE001, PERF203
                traceback.print_exc()
