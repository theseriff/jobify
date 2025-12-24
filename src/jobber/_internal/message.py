from dataclasses import dataclass
from typing import Any

from jobber._internal.configuration import Cron


@dataclass(slots=True, kw_only=True)
class Message:
    route_name: str
    job_id: str
    arguments: dict[str, Any]
    cron: Cron | None = None
    at_timestamp: float | None = None
    options: dict[str, Any]
