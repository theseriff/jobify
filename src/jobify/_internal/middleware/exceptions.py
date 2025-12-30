from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any, TypeAlias, final

from typing_extensions import override

from jobify._internal.context import JobContext
from jobify._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobify._internal.configuration import JobifyConfiguration


ExceptionHandler: TypeAlias = Callable[
    [Exception, JobContext], Awaitable[None] | None
]
ExceptionHandlers: TypeAlias = dict[type[Exception], ExceptionHandler]
MappingExceptionHandlers: TypeAlias = Mapping[
    type[Exception], ExceptionHandler
]


@final
class ExceptionMiddleware(BaseMiddleware):
    __slots__: tuple[str, ...] = ("exc_handlers", "jobify_config")

    def __init__(
        self,
        exc_handlers: ExceptionHandlers,
        jobify_config: JobifyConfiguration,
    ) -> None:
        self.exc_handlers = exc_handlers
        self.jobify_config = jobify_config

    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        try:
            return await call_next(context)
        except Exception as exc:
            handler = self._lookup_exc_handler(exc)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler(exc, context)
                else:
                    loop = self.jobify_config.getloop()
                    thread = self.jobify_config.worker_pools.threadpool
                    await loop.run_in_executor(thread, handler, exc, context)  # pyright: ignore[reportUnusedCallResult]
            raise

    def _lookup_exc_handler(self, exc: Exception) -> ExceptionHandler | None:
        for cls_exc in type(exc).__mro__:
            if handler := self.exc_handlers.get(cls_exc):
                return handler
        return None
