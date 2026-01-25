"""Example of a notification system with Audit middleware.

This module demonstrates how to use middleware to enforce audit logging
for sensitive operations like sending notifications.
"""

import asyncio
import logging
from typing import Any

from typing_extensions import override

from jobify import JobContext, JobRouter
from jobify.middleware import BaseMiddleware, CallNext

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseMiddleware):
    """Middleware that logs an audit record for every executed job."""

    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        job_id = context.job.id
        task_name = context.runnable.name

        # Access job arguments to log specific details
        # We know the 'recipient' argument exists in our tasks below
        arguments = context.runnable.bound.arguments
        recipient: str = arguments.get("recipient", "unknown")

        logger.info(
            "[AUDIT] STARTED: %s (ID: %s) -> Recipient: %s",
            task_name,
            job_id,
            recipient,
        )
        try:
            result = await call_next(context)
        except Exception:
            logger.exception("[AUDIT] FAILED: %s (ID: %s)", task_name, job_id)
            raise
        else:
            logger.info("[AUDIT] SUCCESS: %s (ID: %s)", task_name, job_id)
            return result


notifications_router = JobRouter(prefix="notifications")
notifications_router.add_middleware(AuditMiddleware())


@notifications_router.task
async def send_email_alert(recipient: str, subject: str) -> None:
    """Simulate sending an email alert."""
    logger.info("Connecting to SMTP server for %s...", recipient)
    await asyncio.sleep(0.5)  # Simulate network latency
    logger.info("Email %r sent to %s", subject, recipient)
