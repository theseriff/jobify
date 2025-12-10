from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from jobber._internal.exceptions import JobTimeoutError
from jobber._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobber._internal.context import JobContext

logger = logging.getLogger("jobber.middleware")


class TimeoutMiddleware(BaseMiddleware):
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        timeout = context.route_config.timeout
        try:
            return await asyncio.wait_for(call_next(context), timeout=timeout)
        except asyncio.TimeoutError as exc:
            job_id = context.job.id
            raise JobTimeoutError(job_id=job_id, timeout=timeout) from exc
