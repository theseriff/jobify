# pyright: reportPrivateUsage=false
# ruff: noqa: SLF001
from __future__ import annotations

import asyncio
import logging
import traceback
import warnings
from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Generic, ParamSpec, TypeVar, cast
from uuid import uuid4

from iojobs._internal.constants import EMPTY, ExecutionMode, JobStatus
from iojobs._internal.cron_parser import CronParser
from iojobs._internal.datastructures import State
from iojobs._internal.exceptions import (
    CallbackSkippedError,
    NegativeDelayError,
)
from iojobs._internal.runner.command import (
    AsyncRunner,
    ExecutorPoolRunner,
    SyncRunner,
)
from iojobs._internal.runner.job import Job

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from iojobs._internal._inner_scope import JobInnerScope
    from iojobs._internal.annotations import AnyDict
    from iojobs._internal.func_original import Callback
    from iojobs._internal.middleware.resolver import MiddlewareResolver
    from iojobs._internal.runner.command import Runner


logger = logging.getLogger("iojobs.runner")

ASYNC_FUNC_IGNORED_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""
_ReturnType = TypeVar("_ReturnType")
_FuncParams = ParamSpec("_FuncParams")


@dataclass(slots=True, kw_only=True)
class RunnerContext(Generic[_ReturnType]):
    job: Job[_ReturnType]
    cmd: Runner[_ReturnType]
    execution_mode: ExecutionMode
    cron_parser: CronParser | None


class JobRunner(ABC, Generic[_FuncParams, _ReturnType]):
    __slots__: tuple[str, ...] = (
        "_callback",
        "_cron_parser",
        "_extra",
        "_inner_scope",
        "_jobs_registered",
        "_middleware",
        "_on_error_hooks",
        "_on_success_hooks",
        "_state",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        callback: Callback[_FuncParams, _ReturnType],
        inner_scope: JobInnerScope,
        jobs_registered: dict[str, Job[_ReturnType]],
        on_success_hooks: list[Callable[[_ReturnType], None]],
        on_error_hooks: list[Callable[[Exception], None]],
        middleware: MiddlewareResolver,
        extra: AnyDict,
    ) -> None:
        self._state: State = state
        self._callback: Callback[_FuncParams, _ReturnType] = callback
        self._inner_scope: JobInnerScope = inner_scope
        self._on_success_hooks: list[Callable[[_ReturnType], None]] = (
            on_success_hooks
        )
        self._on_error_hooks: list[Callable[[Exception], None]] = (
            on_error_hooks
        )
        self._jobs_registered: Final = jobs_registered
        self._cron_parser: CronParser = EMPTY
        self._middleware: MiddlewareResolver = middleware
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
        now = now or datetime.now(tz=self._inner_scope.tz)
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
        now = now or datetime.now(tz=self._inner_scope.tz)
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
        self._callback.job_id = job_id
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        cmd = self._get_runner_cmd(exec_mode)
        job = Job(
            exec_at=at,
            job_name=self._callback.job_name,
            job_id=job_id,
            job_registered=self._jobs_registered,
            job_status=JobStatus.SCHEDULED,
            cron_expression=cron_parser._expression if cron_parser else None,
        )
        runner_ctx = RunnerContext(
            job=job,
            cmd=cmd,
            cron_parser=cron_parser,
            execution_mode=exec_mode,
        )
        loop = self._inner_scope.loop
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._execute, runner_ctx)
        job._timer_handler = time_handler
        self._jobs_registered[job_id] = job
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

    def _get_runner_cmd(self, exec_mode: ExecutionMode) -> Runner[_ReturnType]:
        cmd: Runner[_ReturnType]
        if asyncio.iscoroutinefunction(self._callback.original_func):
            c = cast(
                "Callback[_FuncParams, Awaitable[_ReturnType]]",
                self._callback,
            )
            cmd = AsyncRunner(c)
            if exec_mode is ExecutionMode.MAIN:
                return cmd
            if exec_mode is ExecutionMode.PROCESS:
                warn = ASYNC_FUNC_IGNORED_WARNING.format(fname="to_process")
            else:
                warn = ASYNC_FUNC_IGNORED_WARNING.format(fname="to_thread")
            warnings.warn(warn, category=RuntimeWarning, stacklevel=2)
            return cmd

        if exec_mode is ExecutionMode.MAIN:
            return SyncRunner(self._callback)
        executor = (
            self._inner_scope.executors.processpool
            if exec_mode is ExecutionMode.PROCESS
            else self._inner_scope.executors.threadpool
        )
        loop = self._inner_scope.loop
        return ExecutorPoolRunner(self._callback, executor, loop)

    def _execute(self, ctx: RunnerContext[_ReturnType]) -> None:
        task = asyncio.create_task(self._runner(ctx=ctx))
        self._inner_scope.asyncio_tasks.add(task)
        task.add_done_callback(self._inner_scope.asyncio_tasks.discard)

    async def _runner(self, *, ctx: RunnerContext[_ReturnType]) -> None:
        job = ctx.job
        job.status = JobStatus.RUNNING
        self._state.request = State()
        chain = self._middleware.chain(ctx.cmd.run, raise_if_skipped=True)
        try:
            result = await chain(job, self._state)
        except CallbackSkippedError:
            logger.debug("Job %s callback was skipped by middleware", job.id)
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
                _ = self._jobs_registered.pop(job.id)
            event.set()

    async def _reschedule_cron(
        self,
        runner_ctx: RunnerContext[_ReturnType],
    ) -> None:
        cron_parser = cast("CronParser", runner_ctx.cron_parser)
        now = datetime.now(tz=self._inner_scope.tz)
        next_at = cron_parser.next_run(now=now)
        delay_seconds = self._calculate_delay_seconds(now=now, at=next_at)
        loop = self._inner_scope.loop
        when = loop.time() + delay_seconds
        time_handler = loop.call_at(when, self._execute, runner_ctx)
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
