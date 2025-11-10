from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, overload
from zoneinfo import ZoneInfo

from iojobs._internal._inner_context import ExecutorsPool, JobInnerContext
from iojobs._internal.durable.sqlite import SQLiteJobRepository
from iojobs._internal.func_wrapper import FuncWrapper, create_default_name
from iojobs._internal.serializers.json import JSONSerializer

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable, Iterable
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    from iojobs._internal._types import Lifespan
    from iojobs._internal.durable.abc import JobRepository
    from iojobs._internal.job_runner import Job
    from iojobs._internal.serializers.abc import JobsSerializer


_P = ParamSpec("_P")
_R = TypeVar("_R")


class JobScheduler:
    __slots__: tuple[str, ...] = (
        "_func_registered",
        "_inner_ctx",
        "_jobs_registered",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        durable: JobRepository | None = None,
        lifespan: Lifespan | None = None,
        serializer: JobsSerializer | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
    ) -> None:
        _ = lifespan
        self._inner_ctx: JobInnerContext = JobInnerContext(
            _loop=loop,
            tz=tz or ZoneInfo("UTC"),
            durable=durable or SQLiteJobRepository(),
            executors=ExecutorsPool(
                _threadpool=threadpool_executor,
                _processpool=processpool_executor,
            ),
            serializer=serializer or JSONSerializer(),
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
                inner_ctx=self._inner_ctx,
                original_func=func,
                jobs_registered=self._jobs_registered,
            )
            _ = functools.update_wrapper(fwrapper, func)
            self._func_registered[fname] = fwrapper
            return fwrapper

        return wrapper

    @overload
    def register_on_success_hooks(
        self,
        fwrap: FuncWrapper[_P, _R],
        *,
        hooks: Iterable[Callable[[_R], None]],
    ) -> FuncWrapper[_P, _R]: ...

    @overload
    def register_on_success_hooks(
        self,
        *,
        hooks: Iterable[Callable[[_R], None]],
    ) -> Callable[[FuncWrapper[_P, _R]], FuncWrapper[_P, _R]]: ...

    def register_on_success_hooks(
        self,
        fwrap: FuncWrapper[_P, _R] | None = None,
        *,
        hooks: Iterable[Callable[[_R], None]],
    ) -> (
        FuncWrapper[_P, _R]
        | Callable[[FuncWrapper[_P, _R]], FuncWrapper[_P, _R]]
    ):
        f = self._register_on_success_hooks(hooks)
        if callable(fwrap):
            return f(fwrap)
        return f

    def _register_on_success_hooks(
        self,
        callbacks: Iterable[Callable[[_R], None]],
    ) -> Callable[[FuncWrapper[_P, _R]], FuncWrapper[_P, _R]]:
        def wrapper(fwrap: FuncWrapper[_P, _R]) -> FuncWrapper[_P, _R]:
            fwrap._on_success_hooks.extend(callbacks)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            return fwrap

        return wrapper

    @overload
    def register_on_error_hooks(
        self,
        fwrap: FuncWrapper[_P, _R],
        *,
        hooks: Iterable[Callable[[Exception], None]],
    ) -> FuncWrapper[_P, _R]: ...

    @overload
    def register_on_error_hooks(
        self,
        *,
        hooks: Iterable[Callable[[Exception], None]],
    ) -> Callable[[FuncWrapper[_P, _R]], FuncWrapper[_P, _R]]: ...

    def register_on_error_hooks(
        self,
        fwrap: FuncWrapper[_P, _R] | None = None,
        *,
        hooks: Iterable[Callable[[Exception], None]],
    ) -> (
        FuncWrapper[_P, _R]
        | Callable[[FuncWrapper[_P, _R]], FuncWrapper[_P, _R]]
    ):
        f = self._register_on_error_hooks(hooks)
        if callable(fwrap):
            return f(fwrap)
        return f

    def _register_on_error_hooks(
        self,
        callbacks: Iterable[Callable[[Exception], None]],
    ) -> Callable[[FuncWrapper[_P, _R]], FuncWrapper[_P, _R]]:
        def wrapper(fwrap: FuncWrapper[_P, _R]) -> FuncWrapper[_P, _R]:
            fwrap._on_error_hooks.extend(callbacks)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            return fwrap

        return wrapper

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        self._inner_ctx.close()
