from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

from typing_extensions import override

from jobify._internal.router.base import Registrator, Route, Router

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from jobify._internal.common.datastructures import State
    from jobify._internal.common.types import (
        ExceptionHandlers,
        Lifespan,
        MappingExceptionHandlers,
    )
    from jobify._internal.configuration import RouteOptions
    from jobify._internal.middleware.base import (
        BaseMiddleware,
        BaseOuterMiddleware,
    )
    from jobify._internal.scheduler.job import Job
    from jobify._internal.scheduler.scheduler import ScheduleBuilder


ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")
NodeRouter_co = TypeVar("NodeRouter_co", bound="NodeRouter", covariant=True)


class NodeRoute(Route[ParamsT, ReturnT]):
    def __init__(
        self,
        *,
        name: str,
        func: Callable[ParamsT, ReturnT],
        options: RouteOptions,
    ) -> None:
        super().__init__(name, func, options)
        self._real_route: Route[ParamsT, ReturnT] | None = None

    @property
    def real_route(self) -> Route[ParamsT, ReturnT]:
        if self._real_route is None:
            msg = (
                f"Job {self.name!r} is not attached to any Jobify app."
                " Did you forget to call app.include_router()?"
            )
            raise RuntimeError(msg)
        return self._real_route

    def bind(self, route: Route[ParamsT, ReturnT]) -> None:
        self._real_route = route

    @override
    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[ReturnT]:
        return self.real_route.schedule(*args, **kwargs)

    @override
    async def push(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> Job[ReturnT]:
        return await self.real_route.push(*args, **kwargs)


class NodeRegistrator(Registrator[NodeRoute[..., Any]]):
    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State | None,
        lifespan: Lifespan[NodeRouter_co] | None,
        route_class: type[NodeRoute[..., Any]],
        middleware: Sequence[BaseMiddleware] | None,
        outer_middleware: Sequence[BaseOuterMiddleware] | None,
        exception_handlers: MappingExceptionHandlers | None,
    ) -> None:
        super().__init__(
            state=state,
            lifespan=lifespan,
            route_class=route_class,
            middleware=middleware,
            outer_middleware=outer_middleware,
            exception_handlers=exception_handlers,
        )

    @override
    def register(
        self,
        name: str,
        func: Callable[ParamsT, ReturnT],
        options: RouteOptions,
    ) -> NodeRoute[ParamsT, ReturnT]:
        route = self.route_class(name=name, func=func, options=options)
        _ = functools.update_wrapper(route, func)
        self._routes[name] = route
        return cast("NodeRoute[ParamsT, ReturnT]", route)


class NodeRouter(Router):
    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State | None = None,
        prefix: str | None = None,
        lifespan: Lifespan[NodeRouter_co] | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
        outer_middleware: Sequence[BaseOuterMiddleware] | None = None,
        exception_handlers: MappingExceptionHandlers | None = None,
        route_class: type[NodeRoute[..., Any]] = NodeRoute,
    ) -> None:
        super().__init__(prefix=prefix)
        self._registrator: NodeRegistrator = NodeRegistrator(
            state=state,
            lifespan=lifespan,
            middleware=middleware,
            outer_middleware=outer_middleware,
            exception_handlers=exception_handlers,
            route_class=route_class,
        )
        self.state: State = self._registrator.state
        self.exception_handlers: ExceptionHandlers = (
            self._registrator._exception_handlers
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
