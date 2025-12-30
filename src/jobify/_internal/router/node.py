from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

from typing_extensions import override

from jobify._internal.router.base import Registrator, Route, Router

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from jobify._internal.common.datastructures import State
    from jobify._internal.common.types import Lifespan
    from jobify._internal.configuration import RouteOptions
    from jobify._internal.middleware.base import BaseMiddleware
    from jobify._internal.scheduler.scheduler import ScheduleBuilder


ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")
NodeRouter_co = TypeVar("NodeRouter_co", bound="NodeRouter", covariant=True)


class NodeRoute(Route[ParamsT, ReturnT]):
    def __init__(
        self,
        name: str,
        func: Callable[ParamsT, ReturnT],
        options: RouteOptions,
    ) -> None:
        super().__init__(name, func, options)
        self._real_route: Route[ParamsT, ReturnT] | None = None

    def bind(self, route: Route[ParamsT, ReturnT]) -> None:
        self._real_route = route

    @override
    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Any]:
        if self._real_route is None:
            msg = (
                f"Job {self.name!r} is not attached to any Jobify app."
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

    @override
    def register(
        self,
        name: str,
        func: Callable[ParamsT, ReturnT],
        options: RouteOptions,
    ) -> NodeRoute[ParamsT, ReturnT]:
        route = NodeRoute(name, func, options)
        _ = functools.update_wrapper(route, func)
        self._routes[name] = route
        return route


class NodeRouter(Router):
    def __init__(
        self,
        *,
        prefix: str | None = None,
        lifespan: Lifespan[NodeRouter_co] | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
    ) -> None:
        super().__init__(prefix=prefix)
        self._registrator: NodeRegistrator = NodeRegistrator(
            self.state,
            lifespan,
            middleware,
        )

    @property
    @override
    def task(self) -> NodeRegistrator:
        return self._registrator

    @property
    @override
    def routes(self) -> Iterator[NodeRoute[..., Any]]:
        yield from self.task._routes.values()

    @property
    @override
    def sub_routers(self) -> list[NodeRouter]:
        return cast("list[NodeRouter]", self._sub_routers)
