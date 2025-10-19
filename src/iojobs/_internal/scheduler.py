from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, overload
from zoneinfo import ZoneInfo

from iojobs._internal._inner_deps import ExecutorsPool, JobInnerDeps
from iojobs._internal.durable.sqlite import SQLiteJobRepository
from iojobs._internal.func_wrapper import FuncWrapper, create_default_name
from iojobs._internal.serializers.ast_literal import AstLiteralSerializer

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    from iojobs._internal.durable.abc import JobRepository
    from iojobs._internal.job_runner import Job
    from iojobs._internal.serializers.abc import JobsSerializer


_P = ParamSpec("_P")
_R = TypeVar("_R")


class JobScheduler:
    __slots__: tuple[str, ...] = (
        "_func_registered",
        "_inner_deps",
        "_jobs_registered",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        serializer: JobsSerializer | None = None,
        durable: JobRepository | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
    ) -> None:
        self._inner_deps: JobInnerDeps = JobInnerDeps(
            _loop=loop,
            tz=tz or ZoneInfo("UTC"),
            durable=durable or SQLiteJobRepository(),
            executors=ExecutorsPool(
                _threadpool=threadpool_executor,
                _processpool=processpool_executor,
            ),
            serializer=serializer or AstLiteralSerializer(),
            asyncio_tasks=set(),
            extras={},
        )
        self._func_registered: dict[str, FuncWrapper[..., Any]] = {}  # pyright: ignore[reportExplicitAny]
        self._jobs_registered: dict[str, Job[Any]] = {}  # pyright: ignore[reportExplicitAny]

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
            if fwrapper := self._func_registered.get(fname):
                return cast("FuncWrapper[_P, _R]", fwrapper)
            fwrapper = FuncWrapper(
                func_name=fname,
                inner_deps=self._inner_deps,
                original_func=func,
                jobs_registered=self._jobs_registered,
            )
            _ = functools.update_wrapper(fwrapper, func)
            self._func_registered[fname] = fwrapper
            return fwrapper

        return wrapper

    def shutdown(self) -> None:
        self._inner_deps.close()
