# pyright: reportPrivateUsage=false
# ruff: noqa: SLF001
from __future__ import annotations

import asyncio
import traceback
import warnings
from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Generic, TypeVar, cast
from uuid import uuid4

from iojobs._internal.command_runner import (
    AsyncRunner,
    ExecutorPoolRunner,
    SyncRunner,
)
from iojobs._internal.constants import EMPTY, FAILED, ExecutionMode, JobStatus
from iojobs._internal.cron_parser import CronParser
from iojobs._internal.exceptions import (
    JobFailedError,
    JobNotCompletedError,
    NegativeDelayError,
)

if TYPE_CHECKING:
    import functools
    from collections.abc import Callable

    from iojobs._internal._inner_scope import JobInnerScope
    from iojobs._internal.annotations import AnyDict
    from iojobs._internal.command_runner import CommandRunner


ASYNC_FUNC_IGNORED_WARNING = """\
Method {fname!r} is ignored for async functions. \
Use it only with synchronous functions. \
Async functions are already executed in the event loop.
"""

_ReturnType = TypeVar("_ReturnType")


class Job(Generic[_ReturnType]):
    __slots__: tuple[str, ...] = (
        "_event",
        "_exception",
        "_is_was_waiting",
        "_job_registered",
        "_result",
        "_timer_handler",
        "exec_at",
        "func_name",
        "id",
        "status",
    )

    def __init__(
        self,
        *,
        job_id: str,
        exec_at: datetime,
        func_name: str,
        job_registered: dict[str, Job[_ReturnType]],
        job_status: JobStatus,
    ) -> None:
        self._event: asyncio.Event = asyncio.Event()
        self._job_registered: dict[str, Job[_ReturnType]] = job_registered
        self._result: _ReturnType = EMPTY
        self._exception: Exception = EMPTY
        self._is_was_waiting: bool = False
        self._timer_handler: asyncio.TimerHandle = EMPTY
        self.exec_at: datetime = exec_at
        self.func_name: str = func_name
        self.status: JobStatus = job_status
        self.id: str = job_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__qualname__}("
            f"instance_id={id(self)}, "
            f"exec_at={self.exec_at.isoformat()}, "
            f"func_name={self.func_name}, job_id={self.id})"
        )

    def result(self) -> _ReturnType:
        if self._result is FAILED:
            raise JobFailedError(self.id, reason=str(self._exception))
        if self._result is EMPTY:
            raise JobNotCompletedError
        return self._result

    def set_result(self, val: _ReturnType) -> None:
        self._result = val

    def set_exception(self, exc: Exception) -> None:
        self._exception = exc

    def _update(
        self,
        *,
        job_id: str,
        exec_at: datetime,
        job_status: JobStatus,
        time_handler: asyncio.TimerHandle,
    ) -> None:
        self._event = asyncio.Event()
        self._is_was_waiting = False
        self._timer_handler = time_handler
        self.id = job_id
        self.exec_at = exec_at
        self.status = job_status

    def is_done(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        if self._is_was_waiting:
            warnings.warn(
                "Job is already done - waiting for completion is unnecessary",
                category=RuntimeWarning,
                stacklevel=2,
            )
            return

        _ = await self._event.wait()
        self._is_was_waiting = True

    def cancel(self) -> None:
        _ = self._job_registered.pop(self.id, None)
        self.status = JobStatus.CANCELED
        self._timer_handler.cancel()
        self._event.set()


@dataclass(slots=True, kw_only=True)
class RunnerContext(Generic[_ReturnType]):
    job: Job[_ReturnType]
    cmd: CommandRunner[_ReturnType]
    execution_mode: ExecutionMode
    cron_parser: CronParser | None
    asyncio_task: asyncio.Task[_ReturnType] = EMPTY


class JobRunner(ABC, Generic[_ReturnType]):
    __slots__: tuple[str, ...] = (
        "_cron_parser",
        "_extra",
        "_func_injected",
        "_func_name",
        "_inner_scope",
        "_jobs_registered",
        "_on_error_hooks",
        "_on_success_hooks",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        func_name: str,
        inner_scope: JobInnerScope,
        func_injected: functools.partial[_ReturnType],
        jobs_registered: dict[str, Job[_ReturnType]],
        on_success_hooks: list[Callable[[_ReturnType], None]],
        on_error_hooks: list[Callable[[Exception], None]],
        extra: AnyDict,
    ) -> None:
        self._func_name: str = func_name
        self._inner_scope: JobInnerScope = inner_scope
        self._func_injected: functools.partial[_ReturnType] = func_injected
        self._on_success_hooks: list[Callable[[_ReturnType], None]] = (
            on_success_hooks
        )
        self._on_error_hooks: list[Callable[[Exception], None]] = (
            on_error_hooks
        )
        self._jobs_registered: Final = jobs_registered
        self._cron_parser: CronParser = EMPTY
        self._extra: AnyDict = extra

    async def cron(
        self,
        expression: str,
        /,
        *,
        now: datetime | None = None,
        execution_mode: ExecutionMode = ExecutionMode.MAIN,
    ) -> Job[_ReturnType]:
        now = now or datetime.now(tz=self._inner_scope.tz)
        cron_parser = CronParser(expression=expression)
        next_at = cron_parser.next_run(now=now)
        return await self._at(
            now=now,
            at=next_at,
            job_id=uuid4().hex,
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
        delay_seconds = self._calculate_delay_seconds(now=now, at=at)
        cmd = self._get_runner_cmd(exec_mode)
        job = Job(
            exec_at=at,
            func_name=self._func_name,
            job_id=job_id,
            job_registered=self._jobs_registered,
            job_status=JobStatus.SCHEDULED,
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

    def _get_runner_cmd(
        self,
        exec_mode: ExecutionMode,
    ) -> CommandRunner[_ReturnType]:
        cmd: CommandRunner[_ReturnType]
        if asyncio.iscoroutinefunction(self._func_injected):
            cmd = AsyncRunner(self._func_injected)
            if exec_mode is ExecutionMode.MAIN:
                return cmd
            if exec_mode is ExecutionMode.PROCESS:
                warn = ASYNC_FUNC_IGNORED_WARNING.format(fname="to_process")
            else:
                warn = ASYNC_FUNC_IGNORED_WARNING.format(fname="to_thread")
            warnings.warn(warn, category=RuntimeWarning, stacklevel=2)
            return cmd

        func_injected = cast("Callable[..., _ReturnType]", self._func_injected)

        if exec_mode is ExecutionMode.MAIN:
            return SyncRunner(func_injected)
        executor = (
            self._inner_scope.executors.processpool
            if exec_mode is ExecutionMode.PROCESS
            else self._inner_scope.executors.threadpool
        )
        loop = self._inner_scope.loop
        return ExecutorPoolRunner(func_injected, executor, loop)

    def _execute(self, runner_ctx: RunnerContext[_ReturnType]) -> None:
        task = asyncio.create_task(self._runner(runner_ctx=runner_ctx))
        runner_ctx.asyncio_task = task
        self._inner_scope.asyncio_tasks.add(task)

    async def _runner(
        self,
        *,
        runner_ctx: RunnerContext[_ReturnType],
    ) -> _ReturnType:
        job = runner_ctx.job
        cmd = runner_ctx.cmd
        task = runner_ctx.asyncio_task
        try:
            result = await cmd.run()
        except Exception as exc:
            traceback.print_exc()
            job.status = JobStatus.FAILED
            job.set_result(FAILED)
            job.set_exception(exc)
            self._run_hooks_error(exc)
            raise
        else:
            job.set_result(result)
            job.status = JobStatus.SUCCESS
            self._run_hooks_success(result)
            return result
        finally:
            _ = self._jobs_registered.pop(job.id)
            self._inner_scope.asyncio_tasks.discard(task)
            job._event.set()
            if runner_ctx.cron_parser:
                await self._reschedule_cron(runner_ctx)

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
            job_id=uuid4().hex,
            exec_at=next_at,
            time_handler=time_handler,
            job_status=JobStatus.SCHEDULED,
        )
        self._jobs_registered[job.id] = job

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
