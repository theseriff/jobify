from __future__ import annotations

import asyncio
import functools
import os
import sys
from typing import TYPE_CHECKING, Any, Generic, ParamSpec, TypeVar, overload
from uuid import uuid4

from iojobs._internal.durable.sqlite import SQLiteJobRepository
from iojobs._internal.executors_pool import ExecutorPool
from iojobs._internal.job_runner import JobRunnerAsync, JobRunnerSync
from iojobs._internal.serializers.ast_literal import AstLiteralSerializer

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from types import CoroutineType
    from zoneinfo import ZoneInfo

    from iojobs._internal._types import JobExtras
    from iojobs._internal.durable.abc import JobRepository
    from iojobs._internal.job_runner import Job, JobRunner
    from iojobs._internal.serializers.abc import JobsSerializer


_P = ParamSpec("_P")
_R = TypeVar("_R")
_T = TypeVar("_T")


def create_default_name(func: Callable[_P, _R], /) -> str:
    fname = func.__name__
    fmodule = func.__module__
    if fname == "<lambda>":
        fname = f"lambda_{uuid4().hex}"
    if fmodule == "__main__":
        fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
    return f"{fmodule}:{fname}"


class FuncWrapper(Generic[_P, _R]):
    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo,
        loop: asyncio.AbstractEventLoop,
        serializer: JobsSerializer,
        durable: JobRepository,
        func_name: str,
        original_func: Callable[_P, _R],
        asyncio_tasks: list[asyncio.Task[_R]],
        extras: JobExtras,
    ) -> None:
        self._tz: ZoneInfo = tz
        self._loop: asyncio.AbstractEventLoop = loop
        self._executors: ExecutorPool = ExecutorPool()
        self._serializer: JobsSerializer = serializer or AstLiteralSerializer()
        self._durable: JobRepository = durable or SQLiteJobRepository()
        self._func_registered: dict[str, Callable[_P, _R]] = {}
        self._jobs_registered: list[Job[_R]] = []
        self._asyncio_tasks: list[asyncio.Task[_R]] = asyncio_tasks
        self._func_name: str = func_name
        self._extras: JobExtras = extras
        self._original_func: Callable[_P, _R] = original_func
        # This is a hack to make ProcessPoolExecutor work
        # with decorated functions.
        #
        # The problem is that when we decorate a function
        # it becomes a new class. This class has the same
        # name as the original function.
        #
        # When receiver sends original function to another
        # process, it will have the same name as the decorated
        # class. This will cause an error, because ProcessPoolExecutor
        # uses `__name__` and `__qualname__` attributes to
        # import functions from other processes and then it verifies
        # that the function is the same as the original one.
        #
        # This hack renames the original function and injects
        # it back to the module where it was defined.
        # This way ProcessPoolExecutor will be able to import
        # the function by it's name and verify its correctness.
        if original_func.__name__.endswith("iojobs_original"):
            return
        module = sys.modules[original_func.__module__]
        module_attr = getattr(module, original_func.__name__, None)
        if module_attr is original_func:
            return
        new_name = f"{original_func.__name__}__iojobs_original"
        original_func.__name__ = new_name
        if hasattr(original_func, "__qualname__"):  # pragma: no cover
            original_qualname = original_func.__qualname__.rsplit(".", 1)
            original_qualname[-1] = new_name
            new_qualname = ".".join(original_qualname)
            original_func.__qualname__ = new_qualname
        setattr(module, new_name, original_func)

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        return self._original_func(*args, **kwargs)

    @overload
    def schedule(
        self: FuncWrapper[_P, CoroutineType[object, object, _T]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> JobRunnerAsync[_T]: ...

    @overload
    def schedule(
        self: FuncWrapper[_P, Coroutine[object, object, _T]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> JobRunnerAsync[_T]: ...

    @overload
    def schedule(
        self: FuncWrapper[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> JobRunner[_R]: ...

    def schedule(self, *args: _P.args, **kwargs: _P.kwargs) -> JobRunner[Any]:  # pyright: ignore[reportExplicitAny]
        func_injected = functools.partial(self._original_func, *args, **kwargs)
        return (
            JobRunnerAsync(
                tz=self._tz,
                loop=self._loop,
                func_name=self._func_name,
                func_injected=func_injected,
                jobs_registered=self._jobs_registered,
                asyncio_tasks=self._asyncio_tasks,
                extras=self._extras,
            )
            if asyncio.iscoroutinefunction(func_injected)
            else JobRunnerSync(
                tz=self._tz,
                loop=self._loop,
                executors=self._executors,
                func_name=self._func_name,
                func_injected=func_injected,
                jobs_registered=self._jobs_registered,
                asyncio_tasks=self._asyncio_tasks,
                extras=self._extras,
            )
        )
