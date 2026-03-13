from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    import asyncio

    from jobify._internal.scheduler.job import Job


class TaskTracker(NamedTuple):
    pending_jobs: dict[str, Job[Any]]
    pending_tasks: dict[str, asyncio.Task[Any]]
    idle_event: asyncio.Event

    def register_job(self, job: Job[Any]) -> None:
        job._event.clear()
        self.idle_event.clear()
        self.pending_jobs[job.id] = job

    def check_state(self) -> None:
        if not (self.pending_jobs or self.pending_tasks):
            self.idle_event.set()

    def unregister_job(self, job_id: str) -> None:
        if task := self.pending_tasks.pop(job_id, None):
            _ = task.cancel()
        if self.pending_jobs.pop(job_id, None):
            self.check_state()

    def track_task(
        self,
        job_id: str,
        task: asyncio.Task[Any],
        event: asyncio.Event,
    ) -> None:
        self.idle_event.clear()
        self.pending_tasks[job_id] = task
        part = functools.partial(
            self._on_task_done,
            job_id=job_id,
            event=event,
        )
        task.add_done_callback(part)

    def _on_task_done(
        self,
        _t: asyncio.Task[Any],
        *,
        job_id: str,
        event: asyncio.Event,
    ) -> None:
        _ = self.pending_tasks.pop(job_id, None)
        self.check_state()
        event.set()
