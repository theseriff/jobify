from __future__ import annotations

import os
import sys
import uuid
from abc import ABC, abstractmethod
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
from jobber._internal.configuration import Cron, RouteOptions

if TYPE_CHECKING:
    from collections.abc import (
        AsyncIterator,
        Callable,
        Coroutine,
        Iterator,
        Mapping,
        Sequence,
    )
    from types import CoroutineType

    from jobber._internal.common.types import Lifespan
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.scheduler import ScheduleBuilder


ParamsT = ParamSpec("ParamsT")
Return_co = TypeVar("Return_co", covariant=True)
Route_co = TypeVar("Route_co", bound="Route[..., Any]", covariant=True)
Router_co = TypeVar("Router_co", bound="Router", covariant=True)
T_co = TypeVar("T_co", covariant=True)


class Route(ABC, Generic[ParamsT, Return_co]):
    def __init__(
        self,
        func: Callable[ParamsT, Return_co],
        name: str,
        options: RouteOptions,
    ) -> None:
        self.func: Callable[ParamsT, Return_co] = func
        self.name: str = name
        self.options: RouteOptions = options

    def __call__(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> Return_co:
        return self.func(*args, **kwargs)

    @overload
    def schedule(
        self: Route[ParamsT, CoroutineType[object, object, T_co]],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[T_co]: ...

    @overload
    def schedule(
        self: Route[ParamsT, Coroutine[object, object, T_co]],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[T_co]: ...

    @overload
    def schedule(
        self: Route[ParamsT, Return_co],
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Return_co]: ...

    @abstractmethod
    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Any]:
        raise NotImplementedError


@asynccontextmanager
async def dummy_lifespan(_: Router) -> AsyncIterator[None]:
    yield None


def resolve_name(func: Callable[ParamsT, Return_co], /) -> str:
    name = func.__name__
    fmodule = func.__module__
    if name == "<lambda>":
        name = f"lambda_{uuid.uuid4().hex}"
    if fmodule == "__main__":
        fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
    return f"{fmodule}:{name}"


class Registrator(ABC, Generic[Route_co]):
    def __init__(
        self,
        state: State,
        lifespan: Lifespan[Router_co] | None,
        middleware: Sequence[BaseMiddleware] | None,
    ) -> None:
        self._routes: dict[str, Route_co] = {}
        self._lifespan: Final = lifespan or dummy_lifespan
        self._state_lifespan: Final = self._iter_lifespan(self._lifespan)
        self._middleware: list[BaseMiddleware] = list(middleware or [])
        self.state: State = state

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
        func: Callable[ParamsT, Return_co],
    ) -> Route[ParamsT, Return_co]: ...

    @overload
    def __call__(
        self,
        *,
        retry: int = 0,
        timeout: float = 600,
        run_mode: RunMode = EMPTY,
        name: str | None = None,
        cron: str | Cron | None = None,
        durable: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Callable[
        [Callable[ParamsT, Return_co]], Route[ParamsT, Return_co]
    ]: ...

    @overload
    def __call__(
        self,
        func: Callable[ParamsT, Return_co],
        *,
        retry: int = 0,
        timeout: float = 600,
        run_mode: RunMode = EMPTY,
        name: str | None = None,
        cron: str | Cron | None = None,
        durable: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Route[ParamsT, Return_co]: ...

    def __call__(  # noqa: PLR0913
        self,
        func: Callable[ParamsT, Return_co] | None = None,
        *,
        retry: int = 0,
        timeout: float = 600,  # default 10 min.
        run_mode: RunMode = EMPTY,
        name: str | None = None,
        cron: str | Cron | None = None,
        durable: bool | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> (
        Route[ParamsT, Return_co]
        | Callable[[Callable[ParamsT, Return_co]], Route[ParamsT, Return_co]]
    ):
        if isinstance(cron, str):
            cron = Cron(cron)

        route_options = RouteOptions(
            retry=retry,
            timeout=timeout,
            cron=cron,
            run_mode=run_mode,
            name=name,
            durable=durable,
            metadata=metadata,
        )
        wrapper = self._register(route_options)
        if callable(func):
            return wrapper(func)
        return wrapper  # pragma: no cover

    def _register(
        self,
        options: RouteOptions,
    ) -> Callable[[Callable[ParamsT, Return_co]], Route[ParamsT, Return_co]]:
        def wrapper(
            func: Callable[ParamsT, Return_co],
        ) -> Route[ParamsT, Return_co]:
            name = options.name or resolve_name(func)
            return self.register(func, name, options)

        return wrapper

    @abstractmethod
    def register(
        self,
        func: Callable[ParamsT, Return_co],
        name: str,
        options: RouteOptions,
    ) -> Route[ParamsT, Return_co]:
        raise NotImplementedError


class Router(ABC):
    def __init__(
        self,
        *,
        prefix: str | None,
    ) -> None:
        self.state: State = State()
        self.prefix: str = prefix if prefix else ""
        self._parent: Router | None = None
        self._sub_routers: list[Router] = []

    @property
    @abstractmethod
    def task(self) -> Registrator[Route[..., Any]]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"

    @property
    def chain_tail(self) -> Iterator[Router]:
        yield self
        for router in self.sub_routers:
            yield from router.chain_tail

    @property
    def routes(self) -> Iterator[Route[..., Any]]:
        yield from self.task._routes.values()

    @property
    def sub_routers(self) -> Sequence[Router]:
        return self._sub_routers

    @property
    def parent(self) -> Router | None:
        return self._parent

    @parent.setter
    def parent(self, router: Router) -> None:
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

        parent: Router | None = router

        while parent is not None:
            if parent is self:
                msg = "Circular referencing of Router is not allowed"
                raise RuntimeError(msg)
            parent = parent.parent

        self._parent = router

    def include_router(self, router: Router) -> None:
        router.parent = self
        self._sub_routers.append(router)

    def include_routers(self, *routers: Router) -> None:
        if not routers:
            msg = "At least one router must be provided"
            raise ValueError(msg)
        for router in routers:
            self.include_router(router)

    def add_middleware(self, middleware: BaseMiddleware) -> None:
        self.task._middleware.append(middleware)

    def remove_route(self, name: str) -> None:
        del self.task._routes[name]

    def add_route(self, route: Route[..., Any]) -> None:
        self.task._routes[route.name] = route
