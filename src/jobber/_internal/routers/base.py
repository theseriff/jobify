from __future__ import annotations

import os
import sys
import uuid
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Generic,
    ParamSpec,
    TypeVar,
    overload,
)

from jobber._internal.common.constants import EMPTY, RunMode
from jobber._internal.common.datastructures import State
from jobber._internal.configuration import RouteOptions

if TYPE_CHECKING:
    from collections.abc import (
        AsyncIterator,
        Callable,
        Coroutine,
        Mapping,
        Sequence,
    )
    from types import CoroutineType

    from jobber._internal.common.types import Lifespan
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.scheduler import ScheduleBuilder


T = TypeVar("T")
ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")
Route_co = TypeVar("Route_co", bound="Route[..., Any]", covariant=True)
Registrator_co = TypeVar(
    "Registrator_co",
    bound="Registrator[Route[..., Any]]",
    covariant=True,
)


class Route(ABC, Generic[ParamsT, ReturnT]):
    def __init__(
        self,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
    ) -> None:
        self.func: Callable[ParamsT, ReturnT] = func
        self.fname: str = fname
        self.options: RouteOptions = options

    def __call__(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ReturnT:
        return self.func(*args, **kwargs)

    @overload
    def schedule(
        self: Route[ParamsT, CoroutineType[object, object, T]],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[T]: ...

    @overload
    def schedule(
        self: Route[ParamsT, Coroutine[object, object, T]],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[T]: ...

    @overload
    def schedule(
        self: Route[ParamsT, ReturnT],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[ReturnT]: ...

    @abstractmethod
    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Any]:
        raise NotImplementedError


@asynccontextmanager
async def dummy_lifespan(_: Router[Registrator_co]) -> AsyncIterator[None]:
    yield None


def resolve_fname(func: Callable[ParamsT, ReturnT], /) -> str:
    fname = func.__name__
    fmodule = func.__module__
    if fname == "<lambda>":
        fname = f"lambda_{uuid.uuid4().hex}"
    if fmodule == "__main__":
        fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
    return f"{fmodule}:{fname}"


class Registrator(ABC, Generic[Route_co]):
    def __init__(
        self,
        lifespan: Lifespan[T] | None,
        middleware: Sequence[BaseMiddleware] | None,
    ) -> None:
        self._routes: dict[str, Route_co] = {}
        self._lifespan: Final = lifespan or dummy_lifespan
        self._state_lifespan: Final = self._iter_lifespan(self._lifespan)
        self.state: State = State()
        self.middleware: deque[BaseMiddleware] = deque(middleware or [])

    async def _iter_lifespan(
        self,
        user_lifespan: Lifespan[Any],
    ) -> AsyncIterator[None]:
        async with user_lifespan(self) as maybe_state:
            if maybe_state is not None:
                self.state.update(maybe_state)
            yield None

    async def emit_startup(self) -> None:
        await anext(self._state_lifespan)

    async def emit_shutdown(self) -> None:
        await anext(self._state_lifespan, None)

    @overload
    def __call__(
        self,
        func: Callable[ParamsT, ReturnT],
    ) -> Route[ParamsT, ReturnT]: ...

    @overload
    def __call__(
        self,
        *,
        retry: int = 0,
        timeout: float = 600,
        max_cron_failures: int = 10,
        run_mode: RunMode = EMPTY,
        func_name: str | None = None,
        cron: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Callable[[Callable[ParamsT, ReturnT]], Route[ParamsT, ReturnT]]: ...

    @overload
    def __call__(
        self,
        func: Callable[ParamsT, ReturnT],
        *,
        retry: int = 0,
        timeout: float = 600,
        max_cron_failures: int = 10,
        run_mode: RunMode = EMPTY,
        func_name: str | None = None,
        cron: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Route[ParamsT, ReturnT]: ...

    def __call__(  # noqa: PLR0913
        self,
        func: Callable[ParamsT, ReturnT] | None = None,
        *,
        retry: int = 0,
        timeout: float = 600,  # default 10 min.
        max_cron_failures: int = 10,
        run_mode: RunMode = EMPTY,
        func_name: str | None = None,
        cron: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> (
        Route[ParamsT, ReturnT]
        | Callable[[Callable[ParamsT, ReturnT]], Route[ParamsT, ReturnT]]
    ):
        if max_cron_failures < 1:
            msg = (
                "max_cron_failures must be >= 1."
                " Use 1 for 'stop on first error'."
            )
            raise ValueError(msg)

        route_options = RouteOptions(
            retry=retry,
            timeout=timeout,
            max_cron_failures=max_cron_failures,
            run_mode=run_mode,
            func_name=func_name,
            cron=cron,
            metadata=metadata,
        )
        wrapper = self._register(route_options)
        if callable(func):
            return wrapper(func)
        return wrapper  # pragma: no cover

    def _register(
        self,
        options: RouteOptions,
    ) -> Callable[[Callable[ParamsT, ReturnT]], Route[ParamsT, ReturnT]]:
        def wrapper(
            func: Callable[ParamsT, ReturnT],
        ) -> Route[ParamsT, ReturnT]:
            fname = options.func_name or resolve_fname(func)
            return self.register(func, fname, options)

        return wrapper

    @abstractmethod
    def register(
        self,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
    ) -> Route[ParamsT, ReturnT]:
        raise NotImplementedError


class Router(ABC, Generic[Registrator_co]):
    def __init__(
        self,
        *,
        registrator: Registrator_co,
    ) -> None:
        self._parent: Router[Registrator_co] | None = None
        self._sub_routers: list[Router[Registrator_co]] = []
        self.task: Registrator_co = registrator

    @property
    def parent(self) -> Router[Registrator_co] | None:
        return self._parent

    @parent.setter
    def parent(self, router: Router[Registrator_co]) -> None:
        """Set the parent router for this router (internal use only).

        Do not use this method in own code.
        All routers should be included via the `include_router` method.
        Self- and circular-referencing are not allowed here.
        """
        if self._parent:
            msg = f"Router is already attached to {self._parent!r}"
            raise RuntimeError(msg)
        if self is router:
            msg = "Self-referencing routers is not allowed"
            raise RuntimeError(msg)

        parent: Router[Registrator_co] | None = router

        while parent is not None:
            if parent is self:
                msg = "Circular referencing of Router is not allowed"
                raise RuntimeError(msg)
            parent = parent.parent

        self._parent = router

    def include_router(self, router: Router[Registrator_co]) -> None:
        router.parent = self
        self._sub_routers.append(router)

    @abstractmethod
    def add_middleware(self, middleware: BaseMiddleware) -> None:
        self.task.middleware.appendleft(middleware)
