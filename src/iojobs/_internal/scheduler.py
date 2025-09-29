from __future__ import annotations

from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, overload
from zoneinfo import ZoneInfo

from iojobs._internal._types import EMPTY
from iojobs._internal.func_wrapper import FuncWrapper
from iojobs._internal.serializers.ast_literal import AstLiteralSerializer

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from iojobs._internal.job_executor import JobExecutor
    from iojobs._internal.serializers.abc import JobsSerializer


_P = ParamSpec("_P")
_R = TypeVar("_R")


class JobScheduler:
    __slots__: tuple[str, ...] = ("_wrapper",)

    def __init__(
        self,
        *,
        tz: ZoneInfo = EMPTY,
        loop: asyncio.AbstractEventLoop = EMPTY,
        serializer: JobsSerializer = EMPTY,
    ) -> None:
        self._wrapper: FuncWrapper[..., Any] = FuncWrapper(  # pyright: ignore[reportExplicitAny]
            loop=loop,
            tz=tz or ZoneInfo("UTC"),
            serializer=serializer or AstLiteralSerializer(),
        )

    @overload
    def register(
        self,
        func: Callable[_P, _R],
    ) -> Callable[_P, JobExecutor[_R]]: ...

    @overload
    def register(
        self,
        *,
        func_id: str | None = None,
    ) -> Callable[[Callable[_P, _R]], Callable[_P, JobExecutor[_R]]]: ...

    def register(
        self,
        func: Callable[_P, _R] | None = None,
        *,
        func_id: str | None = None,
    ) -> (
        Callable[_P, JobExecutor[_R]]
        | Callable[[Callable[_P, _R]], Callable[_P, JobExecutor[_R]]]
    ):
        wrapper = self._wrapper.register(func_id)
        if callable(func):
            return wrapper(func)
        return wrapper

    async def wait_for_complete(self) -> None:
        jobs_scheduled = self._wrapper.jobs_registered
        try:
            while jobs_scheduled:
                job = jobs_scheduled[0]
                await job.wait()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._wrapper.shutdown()
