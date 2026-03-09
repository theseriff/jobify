from datetime import datetime
from typing import Any, NamedTuple, TypeAlias

from jobify._internal.configuration import Cron

Triggers: TypeAlias = "PushArguments | AtArguments | CronArguments"


class PushArguments(NamedTuple):
    job_id: str


class AtArguments(NamedTuple):
    job_id: str
    at: datetime


class CronArguments(NamedTuple):
    job_id: str
    cron: Cron
    offset: datetime
    run_count: int = 0


class Message(NamedTuple):
    job_id: str
    name: str
    arguments: dict[str, Any]
    trigger: Triggers
