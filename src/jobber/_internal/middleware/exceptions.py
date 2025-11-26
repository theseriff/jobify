import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast, final

from jobber._internal.common.types import (
    ExceptionHandler,
    ExceptionHandlers,
)
from jobber._internal.context import JobContext
from jobber._internal.middleware.base import BaseMiddleware, CallNext


@final
class ExceptionMiddleware(BaseMiddleware):
    __slots__: tuple[str, ...] = ("exc_handlers", "getloop", "threadpool")

    def __init__(
        self,
        exc_handlers: ExceptionHandlers,
        threadpool: ThreadPoolExecutor | None,
        getloop: Callable[[], asyncio.AbstractEventLoop],
    ) -> None:
        self.exc_handlers = exc_handlers
        self.threadpool = threadpool
        self.getloop = getloop

    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:  # noqa: ANN401
        try:
            return await call_next(context)
        except Exception as exc:
            if handler := self._lookup_exc_handler(exc):
                if asyncio.iscoroutinefunction(handler):
                    await handler(context, exc)
                else:
                    loop = self.getloop()
                    thread = self.threadpool
                    handler = cast("Callable[..., None]", handler)
                    await loop.run_in_executor(thread, handler, context, exc)
            raise

    def _lookup_exc_handler(self, exc: Exception) -> ExceptionHandler | None:
        for cls_exc in type(exc).__mro__:
            if handler := self.exc_handlers.get(cls_exc):
                return handler
        return None

    def use(self, cls_exc: type[Exception], handler: ExceptionHandler) -> None:
        self.exc_handlers[cls_exc] = handler
