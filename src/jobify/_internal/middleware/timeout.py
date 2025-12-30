from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import override

from jobify._internal.exceptions import JobTimeoutError
from jobify._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobify._internal.context import JobContext

logger = logging.getLogger("jobify.middleware")


class TimeoutMiddleware(BaseMiddleware):
    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        timeout = context.route_options.get("timeout")
        if timeout is None:
            return await call_next(context)

        try:
            return await asyncio.wait_for(call_next(context), timeout=timeout)
        except asyncio.TimeoutError as exc:
            job_id = context.job.id
            raise JobTimeoutError(job_id=job_id, timeout=timeout) from exc
