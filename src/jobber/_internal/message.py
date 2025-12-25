from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict

from jobber._internal.configuration import Cron


class CronArguments(TypedDict):
    cron: Cron
    job_id: str
    now: datetime


class AtArguments(TypedDict):
    at: datetime
    job_id: str
    now: datetime


@dataclass(slots=True, kw_only=True)
class Message:
    route_name: str
    job_id: str
    arguments: dict[str, Any]
    cron: CronArguments | None = None
    at: AtArguments | None = None
