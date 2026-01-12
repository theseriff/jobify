from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple

from typing_extensions import override

from jobify._internal.cron_parser import CronParser


class GracePolicy(NamedTuple):
    value: timedelta

    @override
    def __str__(self) -> str:
        return f"<{type(self).__name__} value={self.value}>"


class MisfirePolicy(str, Enum):
    ALL = "all"
    SKIP = "skip"
    ONCE = "once"

    @staticmethod
    def GRACE(t: timedelta, /) -> GracePolicy:  # noqa: N802
        return GracePolicy(t)


def handle_misfire_policy(
    cron_parser: CronParser,
    next_run_at: datetime,
    real_now: datetime,
    policy: MisfirePolicy | GracePolicy,
) -> datetime:
    if next_run_at >= real_now:
        return next_run_at

    match policy:
        case MisfirePolicy.ALL:
            return next_run_at
        case MisfirePolicy.SKIP:
            return cron_parser.next_run(now=real_now)
        case MisfirePolicy.ONCE:
            return real_now
        case GracePolicy(value=grace_delta):
            cutoff = real_now - grace_delta
            if next_run_at >= cutoff:
                return next_run_at
            return cron_parser.next_run(now=cutoff)
