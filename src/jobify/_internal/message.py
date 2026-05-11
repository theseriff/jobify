from datetime import datetime
from typing import Any, NamedTuple, TypeAlias

from jobify._internal.configuration import Cron

Triggers: TypeAlias = "PushArguments | AtArguments | CronArguments"


class PushArguments(NamedTuple):
    """Trigger for immediate job execution."""

    job_id: str


class AtArguments(NamedTuple):
    """Trigger for scheduled job execution at a specific time."""

    job_id: str
    at: datetime


class CronArguments(NamedTuple):
    """Trigger for cron-based job execution."""

    job_id: str
    cron: Cron
    offset: datetime
    run_count: int = 0


class Message(NamedTuple):
    """Represents a job message for persistence."""

    job_id: str
    name: str
    arguments: dict[str, Any]
    trigger: Triggers
