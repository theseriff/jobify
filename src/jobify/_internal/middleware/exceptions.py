from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, final

from typing_extensions import override

from jobify._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobify._internal.configuration import JobifyConfiguration
    from jobify._internal.context import JobContext


@final
class ExceptionMiddleware(BaseMiddleware):
    __slots__: tuple[str, ...] = ("jobify_config",)

    def __init__(self, jobify_config: JobifyConfiguration) -> None:
        self.jobify_config = jobify_config

    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        try:
            return await call_next(context)
        except Exception as exc:
            for cls_exc in type(exc).__mro__:
                exc_handlers = context.schedule_builder._exception_handlers
                if handler := exc_handlers.get(cls_exc):
                    break
            else:
                raise

            if asyncio.iscoroutinefunction(handler):
                return await handler(exc, context)

            loop = self.jobify_config.getloop()
            thread = self.jobify_config.worker_pools.threadpool
            return await loop.run_in_executor(thread, handler, exc, context)
