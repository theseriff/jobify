from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

from jobify._internal.configuration import Cron


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
    trigger: CronArguments | AtArguments
