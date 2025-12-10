from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any, TypeAlias, final

from jobber._internal.context import JobContext
from jobber._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobber._internal.configuration import JobberConfiguration


ExceptionHandler: TypeAlias = Callable[
    [JobContext, Exception], Awaitable[None] | None
]
ExceptionHandlers: TypeAlias = dict[type[Exception], ExceptionHandler]
MappingExceptionHandlers: TypeAlias = Mapping[
    type[Exception], ExceptionHandler
]


@final
class ExceptionMiddleware(BaseMiddleware):
    __slots__: tuple[str, ...] = ("exc_handlers", "jobber_config")

    def __init__(
        self,
        exc_handlers: ExceptionHandlers,
        jobber_config: JobberConfiguration,
    ) -> None:
        self.exc_handlers = exc_handlers
        self.jobber_config = jobber_config

    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        try:
            return await call_next(context)
        except Exception as exc:
            handler = self._lookup_exc_handler(exc)
            if asyncio.iscoroutinefunction(handler):
                await handler(context, exc)
            else:
                loop = self.jobber_config.loop_factory()
                thread = self.jobber_config.worker_pools.threadpool
                _ = await loop.run_in_executor(thread, handler, context, exc)
            raise

    def _lookup_exc_handler(self, exc: Exception) -> ExceptionHandler:
        for cls_exc in type(exc).__mro__:
            if handler := self.exc_handlers.get(cls_exc):
                return handler
        raise exc
