from __future__ import annotations

import functools
import os
import sys
from typing import TYPE_CHECKING, Any, Generic, ParamSpec, TypeVar, overload
from uuid import uuid4

from iojobs._internal.job_runner import JobRunner

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from types import CoroutineType

    from iojobs._internal._inner_context import JobInnerContext
    from iojobs._internal.job_runner import Job


_P = ParamSpec("_P")
_R = TypeVar("_R")
_T = TypeVar("_T")


def create_default_name(func: Callable[_P, _R], /) -> str:
    fname = func.__name__
    fmodule = func.__module__
    if fname == "<lambda>":
        fname = f"lambda_{uuid4().hex}"
    if fmodule == "__main__":
        fmodule = sys.argv[0].removesuffix(".py").replace(os.path.sep, ".")
    return f"{fmodule}:{fname}"


class FuncWrapper(Generic[_P, _R]):
    def __init__(
        self,
        *,
        func_name: str,
        inner_ctx: JobInnerContext,
        original_func: Callable[_P, _R],
        jobs_registered: dict[str, Job[_R]],
    ) -> None:
        self._func_name: str = func_name
        self._inner_ctx: JobInnerContext = inner_ctx
        self._jobs_registered: dict[str, Job[_R]] = jobs_registered
        self._on_success_hooks: list[Callable[[_R], None]] = []
        self._on_error_hooks: list[Callable[[Exception], None]] = []
        self._original_func: Callable[_P, _R] = original_func

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
        if original_func.__name__.endswith("iojobs_original"):
            return

        # Guard 2: Check if `register` is used as a decorator (@)
        # or as a direct function call.
        module = sys.modules[original_func.__module__]
        module_attr = getattr(module, original_func.__name__, None)
        if module_attr is original_func:
            return

        # Apply the hack: rename and inject back into the module
        new_name = f"{original_func.__name__}__iojobs_original"
        original_func.__name__ = new_name
        if hasattr(original_func, "__qualname__"):  # pragma: no cover
            original_qualname = original_func.__qualname__.rsplit(".", 1)
            original_qualname[-1] = new_name
            new_qualname = ".".join(original_qualname)
            original_func.__qualname__ = new_qualname
        setattr(module, new_name, original_func)

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        return self._original_func(*args, **kwargs)

    @overload
    def schedule(
        self: FuncWrapper[_P, CoroutineType[object, object, _T]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> JobRunner[_T]: ...

    @overload
    def schedule(
        self: FuncWrapper[_P, Coroutine[object, object, _T]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> JobRunner[_T]: ...

    @overload
    def schedule(
        self: FuncWrapper[_P, _R],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> JobRunner[_R]: ...

    def schedule(self, *args: _P.args, **kwargs: _P.kwargs) -> JobRunner[Any]:  # pyright: ignore[reportExplicitAny]
        func_injected = functools.partial(self._original_func, *args, **kwargs)
        return JobRunner(
            func_name=self._func_name,
            inner_ctx=self._inner_ctx,
            func_injected=func_injected,
            jobs_registered=self._jobs_registered,
            on_success_hooks=self._on_success_hooks,
            on_error_hooks=self._on_error_hooks,
        )
