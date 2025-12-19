from typing import Any, NamedTuple


class JobMessage(NamedTuple):
    name: str
    job_id: str
    args: list[Any]
    kwargs: dict[str, Any]
