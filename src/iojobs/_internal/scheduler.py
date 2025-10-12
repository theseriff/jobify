from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, overload
from zoneinfo import ZoneInfo

from iojobs._internal._types import EMPTY, JobExtras
from iojobs._internal.durable.sqlite import SQLiteJobRepository
from iojobs._internal.executors_pool import ExecutorPool
from iojobs._internal.func_wrapper import FuncWrapper, create_default_name
from iojobs._internal.serializers.ast_literal import AstLiteralSerializer

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from iojobs._internal.durable.abc import JobRepository
    from iojobs._internal.job_runner import Job
    from iojobs._internal.serializers.abc import JobsSerializer


_P = ParamSpec("_P")
_R = TypeVar("_R")


class JobScheduler:
    __slots__: tuple[str, ...] = (
        "_asyncio_tasks",
        "_durable",
        "_executors",
        "_extras",
        "_func_registered",
        "_jobs_registered",
        "_loop",
        "_serializer",
        "_tz",
    )

    def __init__(
        self,
        *,
        tz: ZoneInfo = EMPTY,
        loop: asyncio.AbstractEventLoop = EMPTY,
        serializer: JobsSerializer = EMPTY,
        durable: JobRepository = EMPTY,
    ) -> None:
        self._tz: ZoneInfo = tz or ZoneInfo("UTC")
        self._loop: asyncio.AbstractEventLoop = loop
        self._executors: ExecutorPool = ExecutorPool()
        self._serializer: JobsSerializer = serializer or AstLiteralSerializer()
        self._durable: JobRepository = durable or SQLiteJobRepository()
        self._func_registered: dict[str, Callable[..., Any]] = {}  # pyright: ignore[reportExplicitAny]
        self._jobs_registered: list[Job[Any]] = []  # pyright: ignore[reportExplicitAny]
        self._asyncio_tasks: list[asyncio.Task[Any]] = []  # pyright: ignore[reportExplicitAny]
        self._extras: JobExtras = {}

    @overload
    def register(self, func: Callable[_P, _R]) -> FuncWrapper[_P, _R]: ...

    @overload
    def register(
        self,
        *,
        func_name: str | None = None,
    ) -> Callable[[Callable[_P, _R]], FuncWrapper[_P, _R]]: ...

    @overload
    def register(
        self,
        func: Callable[_P, _R],
        *,
        func_name: str | None = None,
    ) -> FuncWrapper[_P, _R]: ...

    def register(
        self,
        func: Callable[_P, _R] | None = None,
        *,
        func_name: str | None = None,
    ) -> (
        FuncWrapper[_P, _R] | Callable[[Callable[_P, _R]], FuncWrapper[_P, _R]]
    ):
        wrapper = self._register(func_name=func_name)
        if callable(func):
            return wrapper(func)
        return wrapper  # pragma: no cover

    def _register(
        self,
        *,
        func_name: str | None = None,
    ) -> Callable[[Callable[_P, _R]], FuncWrapper[_P, _R]]:
        def wrapper(func: Callable[_P, _R]) -> FuncWrapper[_P, _R]:
            fname = func_name or create_default_name(func)
            fwrapper = FuncWrapper(
                tz=self._tz,
                loop=self._loop,
                serializer=self._serializer,
                durable=self._durable,
                func_name=fname,
                original_func=func,
                asyncio_tasks=self._asyncio_tasks,
                extras=self._extras,
            )
            _ = functools.update_wrapper(fwrapper, func)
            self._func_registered[fname] = fwrapper
            return fwrapper

        return wrapper

    def shutdown(self) -> None:
        self._executors.shutdown()
