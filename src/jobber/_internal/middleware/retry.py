from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from jobber._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobber._internal.context import JobContext

logger = logging.getLogger("jobber.middleware")


class RetryMiddleware(BaseMiddleware):
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        max_retries = context.route_config.retry
        failures = 0
        while True:
            try:
                return await call_next(context)
            except Exception as exc:  # noqa: PERF203
                failures += 1
                if failures > max_retries:
                    msg = (
                        f"Job failed after exhausting all {max_retries}"
                        " retries. Propagating error."
                    )
                    logger.warning(msg)
                    raise

                seconds_wait = min(2 ** (failures - 1), 60)
                logger.warning(
                    "Attempt %s/%s failed. Retrying in %ss. Error: %s",
                    failures,
                    max_retries,
                    seconds_wait,
                    exc,
                )
                await asyncio.sleep(seconds_wait)  # Exponential backoff
