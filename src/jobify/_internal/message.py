from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple, TypeAlias

from jobify._internal.configuration import Cron

Triggers: TypeAlias = "CronArguments | AtArguments | None"


@dataclass(slots=True)
class CronArguments:
    cron: Cron
    job_id: str
    offset: datetime
    run_count: int = 0


class AtArguments(NamedTuple):
    at: datetime
    job_id: str


@dataclass(slots=True, kw_only=True)
class Message:
    job_id: str
    name: str
    arguments: dict[str, Any]
    trigger: Triggers
