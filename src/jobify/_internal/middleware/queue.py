from __future__ import annotations

import asyncio
import logging
from asyncio import Future, PriorityQueue
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol, cast

from typing_extensions import override

from jobify._internal.common.types import UNSET, AppType
from jobify._internal.middleware.base import BaseMiddleware, CallNext
from jobify._internal.plugins import Plugin

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from jobify._internal.context import JobContext

logger = logging.getLogger("jobify.middleware")


class Item(NamedTuple):
    callback: Callable[[], Awaitable[Any]]
    future: Future[Any]
    priority: int = 0

    @override
    def __lt__(self, value: tuple[Any, ...], /) -> bool:
        return self.priority < cast("int", value[2])


_STOP_ITEM = Item(UNSET, UNSET, priority=1 << 31)


class JobifyQueue(Protocol):
    async def get(self) -> Item: ...

    async def put(self, item: Item) -> None: ...
    def task_done(self) -> None: ...


class QueueMiddleware(BaseMiddleware, Plugin[AppType]):
    def __init__(
        self,
        queue: JobifyQueue = UNSET,
        workers: int = 100,
        queue_max_size: int = 1000,
    ) -> None:
        if queue is UNSET:
            queue = PriorityQueue(maxsize=queue_max_size)
        self.queue = queue
        self.workers = workers
        self._workers: tuple[asyncio.Task[None], ...] = UNSET

    async def _worker(self) -> None:
        while True:
            item = await self.queue.get()
            if item is _STOP_ITEM:
                break
            call, fut, _ = item
            try:
                fut.set_result(await call())
            except Exception as exc:  # noqa: BLE001
                fut.set_exception(exc)
            finally:
                self.queue.task_done()

    @override
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        priority = context.route_options.get("metadata", {}).get("priority", 0)
        item = Item(lambda: call_next(context), future=Future(), priority=-priority)
        await self.queue.put(item)
        return await item.future

    @override
    async def startup(self, app: AppType) -> None:
        self._workers = tuple(
            asyncio.create_task(self._worker()) for _ in range(self.workers)
        )

    @override
    async def shutdown(self) -> None:
        for _ in range(self.workers):
            await self.queue.put(_STOP_ITEM)

        await asyncio.gather(*self._workers)
        self._workers = UNSET
