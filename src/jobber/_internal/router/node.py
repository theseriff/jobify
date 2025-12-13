from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

from jobber._internal.common.datastructures import State
from jobber._internal.router.base import Registrator, Route, Router

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from jobber._internal.common.types import Lifespan
    from jobber._internal.configuration import RouteOptions
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.runner.scheduler import ScheduleBuilder


ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")
NodeRouter_co = TypeVar("NodeRouter_co", bound="NodeRouter", covariant=True)


class NodeRoute(Route[ParamsT, ReturnT]):
    def __init__(
        self,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
    ) -> None:
        super().__init__(func, fname, options)
        self._real_route: Route[ParamsT, ReturnT] | None = None

    def bind(self, route: Route[ParamsT, ReturnT]) -> None:
        self._real_route = route

    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Any]:
        if self._real_route is None:
            msg = (
                f"Job {self.fname!r} is not attached to any Jobber app."
                " Did you forget to call app.include_router()?"
            )
            raise RuntimeError(msg)
        return self._real_route.schedule(*args, **kwargs)


class NodeRegistrator(Registrator[NodeRoute[..., Any]]):
    def __init__(
        self,
        state: State,
        lifespan: Lifespan[NodeRouter_co] | None,
        middleware: Sequence[BaseMiddleware] | None,
    ) -> None:
        super().__init__(state, lifespan, middleware)

    def register(
        self,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
    ) -> NodeRoute[ParamsT, ReturnT]:
        if self._routes.get(fname) is None:
            route = NodeRoute(func, fname, options)
            _ = functools.update_wrapper(route, func)
            self._routes[fname] = route

        return cast("NodeRoute[ParamsT, ReturnT]", self._routes[fname])


class NodeRouter(Router):
    def __init__(
        self,
        *,
        prefix: str | None = None,
        lifespan: Lifespan[NodeRouter_co] | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
    ) -> None:
        self.state: State = State()
        super().__init__(
            prefix=prefix,
            registrator=NodeRegistrator(self.state, lifespan, middleware),
        )

    @property
    def task(self) -> NodeRegistrator:
        return cast("NodeRegistrator", self._registrator)

    @property
    def routes(self) -> Iterator[NodeRoute[..., Any]]:
        yield from self.task._routes.values()

    @property
    def sub_routers(self) -> list[NodeRouter]:
        return cast("list[NodeRouter]", self._sub_routers)
