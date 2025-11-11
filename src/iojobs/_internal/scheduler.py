from __future__ import annotations

import functools
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)
from zoneinfo import ZoneInfo

from iojobs._internal._inner_scope import ExecutorsPool, JobInnerScope
from iojobs._internal.datastructures import State
from iojobs._internal.durable.dummy import DummyRepository
from iojobs._internal.durable.sqlite import SQLiteJobRepository
from iojobs._internal.func_wrapper import FuncWrapper, create_default_name
from iojobs._internal.serializers.json import JSONSerializer

if TYPE_CHECKING:
    import asyncio
    from collections.abc import AsyncIterator, Callable, Iterable
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
    from types import TracebackType

    from iojobs._internal.annotations import AnyDict, Lifespan
    from iojobs._internal.durable.abc import JobRepository
    from iojobs._internal.job_runner import Job
    from iojobs._internal.serializers.abc import JobsSerializer


_FuncParams = ParamSpec("_FuncParams")
_ReturnType = TypeVar("_ReturnType")
_AppType = TypeVar("_AppType", bound="JobScheduler")


@asynccontextmanager
async def default_lifespan(_: object) -> AsyncIterator[None]:
    yield None


class JobScheduler:
    def __init__(  # noqa: PLR0913
        self,
        *,
        tz: ZoneInfo | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        durable: JobRepository | Literal[False] | None = None,
        lifespan: Lifespan[_AppType] | None = None,
        serializer: JobsSerializer | None = None,
        threadpool_executor: ThreadPoolExecutor | None = None,
        processpool_executor: ProcessPoolExecutor | None = None,
        **extra: AnyDict,
    ) -> None:
        self.state: State = State()
        if durable is False:
            durable = DummyRepository()
        elif durable is None:
            durable = SQLiteJobRepository()
        self._inner_scope: JobInnerScope = JobInnerScope(
            _loop=loop,
            tz=tz or ZoneInfo("UTC"),
            durable=durable,
            executors=ExecutorsPool(
                _threadpool=threadpool_executor,
                _processpool=processpool_executor,
            ),
            serializer=serializer or JSONSerializer(),
            asyncio_tasks=set(),
        )
        self._lifespan: AsyncIterator[None] = self._lifespan_wrapper(
            lifespan or default_lifespan,
        )
        self._func_registered: dict[str, FuncWrapper[..., Any]] = {}  # pyright: ignore[reportExplicitAny]
        self._jobs_registered: dict[str, Job[Any]] = {}  # pyright: ignore[reportExplicitAny]
        self._extra: AnyDict = extra

    @overload
    def register(
        self,
        func: Callable[_FuncParams, _ReturnType],
    ) -> FuncWrapper[_FuncParams, _ReturnType]: ...

    @overload
    def register(
        self,
        *,
        func_name: str | None = None,
    ) -> Callable[
        [Callable[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]: ...

    @overload
    def register(
        self,
        func: Callable[_FuncParams, _ReturnType],
        *,
        func_name: str | None = None,
    ) -> FuncWrapper[_FuncParams, _ReturnType]: ...

    def register(
        self,
        func: Callable[_FuncParams, _ReturnType] | None = None,
        *,
        func_name: str | None = None,
    ) -> (
        FuncWrapper[_FuncParams, _ReturnType]
        | Callable[
            [Callable[_FuncParams, _ReturnType]],
            FuncWrapper[_FuncParams, _ReturnType],
        ]
    ):
        wrapper = self._register(func_name=func_name)
        if callable(func):
            return wrapper(func)
        return wrapper  # pragma: no cover

    def _register(
        self,
        *,
        func_name: str | None = None,
    ) -> Callable[
        [Callable[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]:
        def wrapper(
            func: Callable[_FuncParams, _ReturnType],
        ) -> FuncWrapper[_FuncParams, _ReturnType]:
            fname = func_name or create_default_name(func)
            if fwrapper := self._func_registered.get(fname):
                return cast("FuncWrapper[_FuncParams, _ReturnType]", fwrapper)
            fwrapper = FuncWrapper(
                func_name=fname,
                inner_scope=self._inner_scope,
                original_func=func,
                jobs_registered=self._jobs_registered,
                extra=self._extra,
            )
            _ = functools.update_wrapper(fwrapper, func)
            self._func_registered[fname] = fwrapper
            return fwrapper

        return wrapper

    @overload
    def register_on_success_hooks(
        self,
        fwrap: FuncWrapper[_FuncParams, _ReturnType],
        *,
        hooks: Iterable[Callable[[_ReturnType], None]],
    ) -> FuncWrapper[_FuncParams, _ReturnType]: ...

    @overload
    def register_on_success_hooks(
        self,
        *,
        hooks: Iterable[Callable[[_ReturnType], None]],
    ) -> Callable[
        [FuncWrapper[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]: ...

    def register_on_success_hooks(
        self,
        fwrap: FuncWrapper[_FuncParams, _ReturnType] | None = None,
        *,
        hooks: Iterable[Callable[[_ReturnType], None]],
    ) -> (
        FuncWrapper[_FuncParams, _ReturnType]
        | Callable[
            [FuncWrapper[_FuncParams, _ReturnType]],
            FuncWrapper[_FuncParams, _ReturnType],
        ]
    ):
        f = self._register_on_success_hooks(hooks)
        if callable(fwrap):
            return f(fwrap)
        return f

    def _register_on_success_hooks(
        self,
        callbacks: Iterable[Callable[[_ReturnType], None]],
    ) -> Callable[
        [FuncWrapper[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]:
        def wrapper(
            fwrap: FuncWrapper[_FuncParams, _ReturnType],
        ) -> FuncWrapper[_FuncParams, _ReturnType]:
            fwrap._on_success_hooks.extend(callbacks)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            return fwrap

        return wrapper

    @overload
    def register_on_error_hooks(
        self,
        fwrap: FuncWrapper[_FuncParams, _ReturnType],
        *,
        hooks: Iterable[Callable[[Exception], None]],
    ) -> FuncWrapper[_FuncParams, _ReturnType]: ...

    @overload
    def register_on_error_hooks(
        self,
        *,
        hooks: Iterable[Callable[[Exception], None]],
    ) -> Callable[
        [FuncWrapper[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]: ...

    def register_on_error_hooks(
        self,
        fwrap: FuncWrapper[_FuncParams, _ReturnType] | None = None,
        *,
        hooks: Iterable[Callable[[Exception], None]],
    ) -> (
        FuncWrapper[_FuncParams, _ReturnType]
        | Callable[
            [FuncWrapper[_FuncParams, _ReturnType]],
            FuncWrapper[_FuncParams, _ReturnType],
        ]
    ):
        f = self._register_on_error_hooks(hooks)
        if callable(fwrap):
            return f(fwrap)
        return f

    def _register_on_error_hooks(
        self,
        callbacks: Iterable[Callable[[Exception], None]],
    ) -> Callable[
        [FuncWrapper[_FuncParams, _ReturnType]],
        FuncWrapper[_FuncParams, _ReturnType],
    ]:
        def wrapper(
            fwrap: FuncWrapper[_FuncParams, _ReturnType],
        ) -> FuncWrapper[_FuncParams, _ReturnType]:
            fwrap._on_error_hooks.extend(callbacks)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            return fwrap

        return wrapper

    async def _lifespan_wrapper(
        self,
        user_lifespan: Lifespan[Any],  # pyright: ignore[reportExplicitAny]
    ) -> AsyncIterator[None]:
        async with user_lifespan(self) as maybe_state:
            if maybe_state is not None:
                self.state.update(maybe_state)
            yield None

    async def __aenter__(self) -> JobScheduler:
        await self.startup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        await self.shutdown()

    async def startup(self) -> None:
        await anext(self._lifespan)

    async def shutdown(self) -> None:
        self._inner_scope.close()
        await anext(self._lifespan, None)
