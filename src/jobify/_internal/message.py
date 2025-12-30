from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict

from jobify._internal.configuration import Cron


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
    job_id: str
    func_name: str
    arguments: dict[str, Any]
    trigger: CronArguments | AtArguments
