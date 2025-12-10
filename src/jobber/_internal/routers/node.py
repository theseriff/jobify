from __future__ import annotations

from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

from jobber._internal.routers.base import (
    Registrator,
    Route,
    Router,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from jobber._internal.common.types import Lifespan
    from jobber._internal.configuration import RouteOptions
    from jobber._internal.middleware.base import BaseMiddleware
    from jobber._internal.routers.root import JobRoute
    from jobber._internal.runner.scheduler import ScheduleBuilder


AppT = TypeVar("AppT")
ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")


class DeferredRoute(Route[ParamsT, ReturnT]):
    def __init__(
        self,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
    ) -> None:
        super().__init__(func, fname, options)
        self._real_route: JobRoute[ParamsT, ReturnT] | None = None

    def bind(self, route: JobRoute[ParamsT, ReturnT]) -> None:
        self._real_route = route

    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Any]:
        if self._real_route is None:
            fname = self.func.__name__
            msg = (
                f"Job {fname!r} is not attached to any Jobber app."
                " Did you forget to call app.include_router()?"
            )
            raise RuntimeError(msg)
        return self._real_route.schedule(*args, **kwargs)


class DeferredRegistrator(Registrator[DeferredRoute[..., Any]]):
    def __init__(
        self,
        prefix: str | None,
        lifespan: Lifespan[AppT] | None,
        middleware: Sequence[BaseMiddleware] | None,
    ) -> None:
        super().__init__(lifespan, middleware)
        self.prefix: str = f"{prefix}:" if prefix else ""

    def register(
        self,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
    ) -> DeferredRoute[ParamsT, ReturnT]:
        fname = f"{self.prefix}{fname}"
        if self._routes.get(fname) is None:
            self._routes[fname] = DeferredRoute(func, fname, options)

        return cast("DeferredRoute[ParamsT, ReturnT]", self._routes[fname])


class DeferredRouter(Router[DeferredRegistrator]):
    def __init__(
        self,
        *,
        prefix: str | None = None,
        lifespan: Lifespan[AppT] | None = None,
        middleware: Sequence[BaseMiddleware] | None = None,
    ) -> None:
        super().__init__(
            registrator=DeferredRegistrator(
                prefix,
                lifespan,
                middleware,
            ),
        )

    def add_middleware(self, middleware: BaseMiddleware) -> None:
        return super().add_middleware(middleware)
