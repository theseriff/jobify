from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jobify._internal.scheduler.job import Job


@dataclass(slots=True, kw_only=True, frozen=True)
class SharedState:
    pending_jobs: dict[str, Job[Any]] = field(default_factory=dict)
    pending_tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    idle_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self.idle_event.set()

    def register_job(self, job: Job[Any]) -> None:
        job._event.clear()
        self.idle_event.clear()
        self.pending_jobs[job.id] = job

    def unregister_job(self, job_id: str) -> None:
        if self.pending_jobs.pop(job_id, None):
            self._check_state()

    def track_task(
        self,
        task: asyncio.Task[Any],
        event: asyncio.Event,
    ) -> None:
        self.idle_event.clear()
        self.pending_tasks.add(task)
        part = functools.partial(self._on_task_done, event=event)
        task.add_done_callback(part)

    def _on_task_done(
        self,
        task: asyncio.Task[Any],
        event: asyncio.Event,
    ) -> None:
        self.pending_tasks.discard(task)
        self._check_state()
        event.set()

    def _check_state(self) -> None:
        if not (self.pending_jobs or self.pending_tasks):
            self.idle_event.set()
