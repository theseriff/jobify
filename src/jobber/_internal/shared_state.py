from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio

    from jobber._internal.runner.job import Job


@dataclass(slots=True, kw_only=True, frozen=True)
class SharedState:
    pending_jobs: dict[str, Job[Any]] = field(default_factory=dict)
    pending_tasks: set[asyncio.Task[Any]] = field(default_factory=set)
