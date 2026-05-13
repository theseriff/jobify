from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import override

from jobify._internal.configuration import SmartRetry
from jobify._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobify._internal.context import JobContext

logger = logging.getLogger("jobify.middleware")


class RetryMiddleware(BaseMiddleware):
    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        cfg = context.route_options.get("retry")
        if not isinstance(cfg, SmartRetry):
            return await call_next(context)

        attempt = 0
        while True:
            try:
                return await call_next(context)
            except cfg.exclude_exceptions:  # noqa: PERF203
                raise
            except cfg.include_exceptions as exc:
                attempt += 1
                if attempt > cfg.retries:
                    msg = (
                        f"Job failed after exhausting all {cfg.retries}"
                        " retries. Propagating error."
                    )
                    logger.warning(msg)
                    raise

                delay = cfg.compute_delay(attempt)
                logger.warning(
                    "Attempt %s/%s failed. Retrying in %ss. Error: %s",
                    attempt,
                    cfg.retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
