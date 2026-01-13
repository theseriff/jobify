from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

from jobify._internal.configuration import Cron


class CronArguments(NamedTuple):
    cron: Cron
    job_id: str
    offset: datetime


class AtArguments(NamedTuple):
    at: datetime
    job_id: str


@dataclass(slots=True, kw_only=True)
class Message:
    job_id: str
    func_name: str
    arguments: dict[str, Any]
    trigger: CronArguments | AtArguments
