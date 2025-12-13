from __future__ import annotations

import asyncio
import functools
import sys
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

from jobber._internal.common.datastructures import State
from jobber._internal.exceptions import (
    raise_app_already_started_error,
    raise_app_not_started_error,
)
from jobber._internal.injection import inject_context
from jobber._internal.middleware.base import build_middleware
from jobber._internal.middleware.exceptions import ExceptionMiddleware
from jobber._internal.middleware.retry import RetryMiddleware
from jobber._internal.middleware.timeout import TimeoutMiddleware
from jobber._internal.router.base import Registrator, Route, Router
from jobber._internal.runner.runners import Runnable, create_run_strategy
from jobber._internal.runner.scheduler import ScheduleBuilder

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from jobber._internal.common.types import Lifespan
    from jobber._internal.configuration import (
        JobberConfiguration,
        RouteOptions,
    )
    from jobber._internal.context import JobContext
    from jobber._internal.middleware.base import BaseMiddleware, CallNext
    from jobber._internal.middleware.exceptions import (
        ExceptionHandler,
        ExceptionHandlers,
        MappingExceptionHandlers,
    )
    from jobber._internal.router.node import NodeRouter
    from jobber._internal.runner.runners import RunStrategy


ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")
RootRouter_co = TypeVar("RootRouter_co", bound="RootRouter", covariant=True)

PENDING_CRON_JOBS = "__pending_cron_jobs__"


class RootRoute(Route[ParamsT, ReturnT]):
    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
        strategy: RunStrategy[ParamsT, ReturnT],
        jobber_config: JobberConfiguration,
    ) -> None:
        super().__init__(func, fname, options)
        self._strategy_run: RunStrategy[ParamsT, ReturnT] = strategy
        self._chain_middleware: CallNext | None = None
        self.jobber_config: JobberConfiguration = jobber_config
        self.state: State = state

        # --------------------------------------------------------------------
        # HACK: ProcessPoolExecutor / Multiprocessing  # noqa: ERA001, FIX004
        #
        # Problem: `ProcessPoolExecutor` (used for ExecutionMode.PROCESS)
        # serializes the function by its name. When we use `@register`
        # as a decorator, the function's name in the module (`my_func`)
        # now points to the `FuncWrapper` object, not the original function.
        # This breaks `pickle`.
        #
        # Solution: We rename the *original* function (adding a suffix)
        # and "inject" it back into its own module under this new
        # name. This way, `ProcessPoolExecutor` can find and pickle it.
        #
        # We DO NOT apply this hack in two cases (Guard Clauses):
        # 1. If `register` is used as a direct function call (`reg(my_func)`),
        #    because `my_func` in the module still points to the original.
        # 2. If the function has already been renamed (protects from re-entry).
        # --------------------------------------------------------------------

        # Guard 1: Protect against double-renaming
        if func.__name__.endswith("jobber_original"):
            return

        # Guard 2: Check if `register` is used as a decorator (@)
        # or as a direct function call.
        module = sys.modules[func.__module__]
        module_attr = getattr(module, func.__name__, None)
        if module_attr is func:
            return

        # Apply the hack: rename and inject back into the module
        new_name = f"{func.__name__}__jobber_original"
        func.__name__ = new_name
        if hasattr(func, "__qualname__"):  # pragma: no cover
            original_qualname = func.__qualname__.rsplit(".", 1)
            original_qualname[-1] = new_name
            new_qualname = ".".join(original_qualname)
            func.__qualname__ = new_qualname
        setattr(module, new_name, func)

    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Any]:
        if not (self.jobber_config.app_started and self._chain_middleware):
            raise_app_not_started_error("schedule")

        return ScheduleBuilder(
            state=self.state,
            options=self.options,
            func_name=self.fname,
            jobber_config=self.jobber_config,
            chain_middleware=self._chain_middleware,
            runnable=self._strategy_run.create_runnable(*args, **kwargs),
        )


class RootRegistrator(Registrator[RootRoute[..., Any]]):
    def __init__(
        self,
        state: State,
        lifespan: Lifespan[RootRouter_co] | None,
        middleware: Sequence[BaseMiddleware] | None,
        jobber_config: JobberConfiguration,
        exception_handlers: MappingExceptionHandlers | None,
    ) -> None:
        super().__init__(state, lifespan, middleware)
        self._exc_handlers: ExceptionHandlers = dict(exception_handlers or {})
        self.jobber_config: JobberConfiguration = jobber_config

        for system_middleware in (
            TimeoutMiddleware(),
            RetryMiddleware(),
            ExceptionMiddleware(self._exc_handlers, self.jobber_config),
        ):
            self._middleware.insert(0, system_middleware)

    def register(
        self,
        func: Callable[ParamsT, ReturnT],
        fname: str,
        options: RouteOptions,
    ) -> RootRoute[ParamsT, ReturnT]:
        if self.jobber_config.app_started is True:
            raise_app_already_started_error("register")

        if self._routes.get(fname) is None:
            strategy = create_run_strategy(
                func,
                self.jobber_config,
                mode=options.run_mode,
            )
            route = RootRoute(
                func=func,
                state=self.state,
                options=options,
                fname=fname,
                strategy=strategy,
                jobber_config=self.jobber_config,
            )
            _ = functools.update_wrapper(route, func)
            self._routes[fname] = route
            if options.cron:
                p = (route, options.cron)
                self.state.setdefault(PENDING_CRON_JOBS, []).append(p)

        return cast("RootRoute[ParamsT, ReturnT]", self._routes[fname])

    async def start_crons(self) -> None:
        if crons := self.state.pop(PENDING_CRON_JOBS, []):
            pending = (route.schedule().cron(cron) for route, cron in crons)
            _ = await asyncio.gather(*pending)


class RootRouter(Router):
    def __init__(
        self,
        *,
        lifespan: Lifespan[RootRouter_co] | None,
        middleware: Sequence[BaseMiddleware] | None,
        jobber_config: JobberConfiguration,
        exception_handlers: MappingExceptionHandlers | None,
    ) -> None:
        self.state: State = State()
        super().__init__(
            prefix=None,
            registrator=RootRegistrator(
                self.state,
                lifespan,
                middleware,
                jobber_config,
                exception_handlers,
            ),
        )

    @property
    def task(self) -> RootRegistrator:
        return cast("RootRegistrator", self._registrator)

    def add_exception_handler(
        self,
        cls_exc: type[Exception],
        handler: ExceptionHandler,
    ) -> None:
        if self.task.jobber_config.app_started is True:
            raise_app_already_started_error("add_exception_handler")
        self.task._exc_handlers[cls_exc] = handler

    def add_middleware(self, middleware: BaseMiddleware) -> None:
        if self.task.jobber_config.app_started is True:
            raise_app_already_started_error("add_middleware")
        super().add_middleware(middleware)

    def include_router(self, router: Router) -> None:
        super().include_router(router)
        self._propagate_real_routes(self)

    def _propagate_real_routes(self, router: Router) -> None:
        parent = cast("NodeRouter", router)
        for sub_router in parent.sub_routers:
            sub_router.propagate_prefix(parent)
            for route in tuple(sub_router.routes):
                sub_router.remove_route(route.fname)
                route.fname = f"{sub_router.prefix}:{route.fname}"
                real_route = self.task.register(
                    route.func,
                    route.fname,
                    route.options,
                )
                route.bind(real_route)
                sub_router.set_route(real_route)
            self._propagate_real_routes(sub_router)

    async def _propagate_startup(self, router: Router) -> None:
        await router._registrator.emit_startup()
        chain = build_middleware(router._registrator._middleware, self._entry)
        for route in cast("Iterator[RootRoute[..., Any]]", router.routes):
            route.state = router.task.state
            route._chain_middleware = chain

        for sub_router in router.sub_routers:
            sub_router.task.state.update(
                router.task.state | sub_router.task.state
            )
            sub_router.task._middleware = [
                *router.task._middleware,
                *sub_router.task._middleware,
            ]
            await self._propagate_startup(sub_router)

    async def _propagate_shutdown(self) -> None:
        for router in self.chain_tail:
            await router.task.emit_shutdown()

    async def _entry(self, context: JobContext) -> Any:  # noqa: ANN401
        runnable: Runnable[Any] = context.runnable
        inject_context(runnable, context)
        return await runnable()
