from __future__ import annotations

import os
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    ParamSpec,
    TypeVar,
    final,
    overload,
)
from uuid import uuid4

from jobber._internal.middleware.base import (
    BaseMiddleware,
    MiddlewarePipeline,
)
from jobber._internal.runner.executor import Executor
from jobber._internal.runner.runnable import Runnable
from jobber._internal.runner.scheduler import ScheduleBuilder

if TYPE_CHECKING:
    from collections import deque
    from collections.abc import Callable, Coroutine
    from types import CoroutineType

    from jobber._internal.common.constants import ExecutionMode
    from jobber._internal.common.datastructures import State
    from jobber._internal.context import AppContext
    from jobber._internal.runner.job import Job


_FuncParams = ParamSpec("_FuncParams")
_ReturnType = TypeVar("_ReturnType")
_T = TypeVar("_T")


def create_default_name(func: Callable[_FuncParams, _ReturnType], /) -> str:
    fname = func.__name__
    fmodule = func.__module__
    if fname == "<lambda>":
        fname = f"lambda_{uuid4().hex}"
    if fmodule == "__main__":
        fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
    return f"{fmodule}:{fname}"


@final
class Route(Generic[_FuncParams, _ReturnType]):
    def __init__(  # noqa: PLR0913
        self,
        *,
        state: State,
        job_name: str,
        app_ctx: AppContext,
        original_func: Callable[_FuncParams, _ReturnType],
        exec_mode: ExecutionMode,
        job_registry: dict[str, Job[_ReturnType]],
        user_middleware: deque[BaseMiddleware],
    ) -> None:
        self._state = state
        self._app_ctx = app_ctx
        self._job_name = job_name
        self._exec_mode = exec_mode
        self._job_registry = job_registry
        self._original_func = original_func
        self._middleware_chain = MiddlewarePipeline(
            user_middleware,
        ).build_chain(
            Executor[_ReturnType](
                worker_pools=app_ctx.worker_pools,
                getloop=app_ctx.getloop,
            )
        )

        # --------------------------------------------------------------------
        # HACK: ProcessPoolExecutor / Multiprocessing
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
        if original_func.__name__.endswith("jobber_original"):
            return

        # Guard 2: Check if `register` is used as a decorator (@)
        # or as a direct function call.
        module = sys.modules[original_func.__module__]
        module_attr = getattr(module, original_func.__name__, None)
        if module_attr is original_func:
            return

        # Apply the hack: rename and inject back into the module
        new_name = f"{original_func.__name__}__jobber_original"
        original_func.__name__ = new_name
        if hasattr(original_func, "__qualname__"):  # pragma: no cover
            original_qualname = original_func.__qualname__.rsplit(".", 1)
            original_qualname[-1] = new_name
            new_qualname = ".".join(original_qualname)
            original_func.__qualname__ = new_qualname
        setattr(module, new_name, original_func)

    def __call__(
        self,
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> _ReturnType:
        return self._original_func(*args, **kwargs)

    @overload
    def schedule(
        self: Route[_FuncParams, CoroutineType[object, object, _T]],
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> ScheduleBuilder[_T]: ...

    @overload
    def schedule(
        self: Route[_FuncParams, Coroutine[object, object, _T]],
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> ScheduleBuilder[_T]: ...

    @overload
    def schedule(
        self: Route[_FuncParams, _ReturnType],
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> ScheduleBuilder[_ReturnType]: ...

    def schedule(
        self,
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> ScheduleBuilder[Any]:
        runnable = Runnable(
            self._original_func,
            self._exec_mode,
            *args,
            **kwargs,
        )
        return ScheduleBuilder(
            app_ctx=self._app_ctx,
            runnable=runnable,
            job_name=self._job_name,
            job_registry=self._job_registry,
            middleware_chain=self._middleware_chain,
            state=self._state,
        )
