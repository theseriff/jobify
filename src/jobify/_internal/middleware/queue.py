from __future__ import annotations

import asyncio
import logging
from asyncio import Future, PriorityQueue
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

from typing_extensions import override

from jobify._internal.common.constants import UNSET
from jobify._internal.middleware.base import BaseMiddleware, CallNext

if TYPE_CHECKING:
    from jobify._internal.common.types import AppType
    from jobify._internal.context import JobContext

logger = logging.getLogger("jobify.middleware")


class Item(NamedTuple):
    call_next: CallNext
    context: JobContext
    future: Future[Any]
    priority: int = 0

    @override
    def __lt__(self, value: tuple[Any, ...], /) -> bool:
        other_priority: int = value[-1]
        return self.priority < other_priority


_STOP_ITEM = Item(UNSET, UNSET, UNSET, priority=1 << 31)


class JobifyQueue(Protocol):
    async def get(self) -> Item: ...
    async def put(self, item: Item) -> None: ...
    def task_done(self) -> None: ...


class QueueMiddleware(BaseMiddleware):
    def __init__(self, queue: JobifyQueue = UNSET, workers: int = 100) -> None:
        if queue is UNSET:
            queue = PriorityQueue(maxsize=1024)
        self.queue: JobifyQueue = queue
        self.workers: int = workers
        self._workers: tuple[asyncio.Task[None], ...] = UNSET

    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        priority = context.route_options.get("metadata", {}).get("priority", 0)
        item = Item(call_next, context, future=Future(), priority=-priority)
        await self.queue.put(item)
        return await item.future

    async def startup(self, _: AppType) -> None:
        self._workers = tuple(
            asyncio.create_task(self._worker()) for _ in range(self.workers)
        )

    async def shutdown(self) -> None:
        for _ in range(self.workers):
            await self.queue.put(_STOP_ITEM)
        await asyncio.gather(*self._workers)
        self._workers = UNSET

    async def _worker(self) -> None:
        while True:
            item = await self.queue.get()
            if item is _STOP_ITEM:
                self.queue.task_done()
                break

            call_next, context, fut, _ = item
            try:
                fut.set_result(await call_next(context))
            except Exception as exc:  # noqa: BLE001
                fut.set_exception(exc)
            finally:
                self.queue.task_done()
