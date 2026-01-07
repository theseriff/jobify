from __future__ import annotations

import functools
import logging
import sys
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, get_type_hints

from typing_extensions import override

from jobify._internal.common.constants import PATCH_SUFFIX
from jobify._internal.configuration import Cron
from jobify._internal.exceptions import (
    raise_app_already_started_error,
    raise_app_not_started_error,
)
from jobify._internal.injection import inject_context
from jobify._internal.inspection import FuncSpec, make_func_spec
from jobify._internal.middleware.base import build_middleware
from jobify._internal.middleware.exceptions import ExceptionMiddleware
from jobify._internal.middleware.retry import RetryMiddleware
from jobify._internal.middleware.timeout import TimeoutMiddleware
from jobify._internal.router.base import Registrator, Route, Router
from jobify._internal.runners import Runnable, create_run_strategy
from jobify._internal.scheduler.scheduler import ScheduleBuilder
from jobify._internal.serializers.json_extended import ExtendedJSONSerializer

if TYPE_CHECKING:
    import inspect
    from collections.abc import Callable, Iterator, Sequence

    from jobify._internal.common.datastructures import State
    from jobify._internal.common.types import Lifespan
    from jobify._internal.configuration import (
        JobifyConfiguration,
        RouteOptions,
    )
    from jobify._internal.context import JobContext
    from jobify._internal.middleware.base import BaseMiddleware, CallNext
    from jobify._internal.middleware.exceptions import (
        ExceptionHandler,
        ExceptionHandlers,
        MappingExceptionHandlers,
    )
    from jobify._internal.router.node import NodeRouter
    from jobify._internal.runners import RunStrategy
    from jobify._internal.shared_state import SharedState


logger = logging.getLogger("Jobify.router")

ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")
RootRouter_co = TypeVar("RootRouter_co", bound="RootRouter", covariant=True)

PENDING_CRON_JOBS = "__pending_cron_jobs__"


class RootRoute(Route[ParamsT, ReturnT]):
    def __init__(  # noqa: PLR0913
        self,
        *,
        name: str,
        func: Callable[ParamsT, ReturnT],
        func_spec: FuncSpec[ReturnT],
        state: State,
        options: RouteOptions,
        strategy: RunStrategy[ParamsT, ReturnT],
        shared_state: SharedState,
        jobify_config: JobifyConfiguration,
    ) -> None:
        super().__init__(name, func, options)
        self._run_strategy: RunStrategy[ParamsT, ReturnT] = strategy
        self._chain_middleware: CallNext | None = None
        self._shared_state: SharedState = shared_state
        self.state: State = state
        self.func_spec: FuncSpec[ReturnT] = func_spec
        self.jobify_config: JobifyConfiguration = jobify_config

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
        if func.__name__.endswith(PATCH_SUFFIX):
            return

        # Guard 2: Check if `register` is used as a decorator (@)
        # or as a direct function call.
        module = sys.modules[func.__module__]
        module_attr = getattr(module, func.__name__, None)
        if module_attr is func:
            return

        # Apply the hack: rename and inject back into the module
        new_name = f"{func.__name__}{PATCH_SUFFIX}"
        func.__name__ = new_name
        if hasattr(func, "__qualname__"):  # pragma: no cover
            original_qualname = func.__qualname__.rsplit(".", 1)
            original_qualname[-1] = new_name
            new_qualname = ".".join(original_qualname)
            func.__qualname__ = new_qualname
        setattr(module, new_name, func)

    @override
    def schedule(
        self,
        *args: ParamsT.args,
        **kwargs: ParamsT.kwargs,
    ) -> ScheduleBuilder[Any]:
        bound = self.func_spec.signature.bind(*args, **kwargs)
        return self.create_builder(bound)

    def create_builder(
        self,
        bound: inspect.BoundArguments,
        /,
    ) -> ScheduleBuilder[Any]:
        if not (self.jobify_config.app_started and self._chain_middleware):
            raise_app_not_started_error("schedule")
        return ScheduleBuilder(
            state=self.state,
            options=self.options,
            func_name=self.name,
            func_spec=self.func_spec,
            shared_state=self._shared_state,
            jobify_config=self.jobify_config,
            chain_middleware=self._chain_middleware,
            runnable=Runnable(self._run_strategy, bound),
        )


class RootRegistrator(Registrator[RootRoute[..., Any]]):
    def __init__(  # noqa: PLR0913
        self,
        state: State,
        lifespan: Lifespan[RootRouter_co] | None,
        middleware: Sequence[BaseMiddleware] | None,
        shared_state: SharedState,
        jobify_config: JobifyConfiguration,
        exception_handlers: MappingExceptionHandlers | None,
    ) -> None:
        super().__init__(state, lifespan, middleware)
        self._shared_state: SharedState = shared_state
        self._exc_handlers: ExceptionHandlers = dict(exception_handlers or {})
        self._jobify_config: JobifyConfiguration = jobify_config
        self._system_middleware: list[BaseMiddleware] = [
            ExceptionMiddleware(self._exc_handlers, jobify_config),
            RetryMiddleware(),
            TimeoutMiddleware(),
        ]

    @override
    def register(
        self,
        name: str,
        func: Callable[ParamsT, ReturnT],
        options: RouteOptions,
    ) -> RootRoute[ParamsT, ReturnT]:
        if self._jobify_config.app_started is True:
            raise_app_already_started_error("register")

        if isinstance(self._jobify_config.serializer, ExtendedJSONSerializer):
            hints = get_type_hints(func)
            self._jobify_config.serializer.registry_types(hints.values())

        strategy = create_run_strategy(
            func,
            self._jobify_config,
            mode=options.get("run_mode"),
        )
        route = RootRoute(
            name=name,
            func=func,
            func_spec=make_func_spec(func),
            state=self.state,
            options=options,
            strategy=strategy,
            shared_state=self._shared_state,
            jobify_config=self._jobify_config,
        )
        _ = functools.update_wrapper(route, func)
        self._routes[name] = route

        if cron := options.get("cron"):
            if isinstance(cron, str):
                cron = Cron(cron)
            job_id = f"{route.name}__jobify_cron_definition"
            p = (route, cron, job_id)
            self.state.setdefault(PENDING_CRON_JOBS, []).append(p)

        return route

    async def start_pending_crons(self) -> None:
        for route, cron, job_id in self.state.pop(PENDING_CRON_JOBS, []):
            if job_id in self._shared_state.pending_jobs:
                continue  # Skip if already scheduled
            builder: ScheduleBuilder[Any] = route.schedule()
            _ = await builder.cron(cron=cron, job_id=job_id, now=builder.now())


class RootRouter(Router):
    def __init__(
        self,
        *,
        lifespan: Lifespan[RootRouter_co] | None,
        middleware: Sequence[BaseMiddleware] | None,
        shared_state: SharedState,
        jobify_config: JobifyConfiguration,
        exception_handlers: MappingExceptionHandlers | None,
    ) -> None:
        super().__init__(prefix=None)
        self._registrator: RootRegistrator = RootRegistrator(
            self.state,
            lifespan,
            middleware,
            shared_state,
            jobify_config,
            exception_handlers,
        )

    @property
    @override
    def task(self) -> RootRegistrator:
        return self._registrator

    def add_exception_handler(
        self,
        cls_exc: type[Exception],
        handler: ExceptionHandler,
    ) -> None:
        if self.task._jobify_config.app_started is True:
            raise_app_already_started_error("add_exception_handler")
        self.task._exc_handlers[cls_exc] = handler

    @override
    def add_middleware(self, middleware: BaseMiddleware) -> None:
        if self.task._jobify_config.app_started is True:
            raise_app_already_started_error("add_middleware")
        super().add_middleware(middleware)

    @override
    def include_router(self, router: Router) -> None:
        super().include_router(router)
        self._propagate_real_routes(cast("NodeRouter", router))

    def _propagate_real_routes(self, router: NodeRouter) -> None:
        for route in tuple(router.routes):
            router.remove_route(route.name)
            prefix = f"{router.prefix}:" if router.prefix else ""
            route.name = f"{prefix}{route.name}"
            real_route = self.task.register(
                route.name,
                route.func,
                route.options,
            )
            route.bind(real_route)
            router.add_route(real_route)

        for sub_router in router.sub_routers:
            suffix = f".{sub_router.prefix}" if sub_router.prefix else ""
            sub_router.prefix = f"{router.prefix}{suffix}"
            self._propagate_real_routes(sub_router)

    async def _propagate_startup(self, router: Router) -> None:
        await router.task.emit_startup()

        final_middleware = [
            *router.task._middleware,
            *self.task._system_middleware,
        ]
        chain = build_middleware(final_middleware, self._entry)
        for route in cast("Iterator[RootRoute[..., Any]]", router.routes):
            route.state = router.task.state
            route._chain_middleware = chain

        for sub_router in router.sub_routers:
            sub_router.task.state = router.task.state | sub_router.task.state
            sub_router.task._middleware = [
                *router.task._middleware,
                *sub_router.task._middleware,
            ]
            await self._propagate_startup(sub_router)

    async def _propagate_shutdown(self) -> None:
        for router in self.chain_tail:
            await router.task.emit_shutdown()

    async def _entry(self, context: JobContext) -> Any:  # noqa: ANN401
        inject_context(context)
        return await context.runnable()
