import inspect
import warnings
from collections.abc import Awaitable, Callable
from typing import Generic, ParamSpec, TypeGuard, TypeVar, final

from jobber._internal.common.constants import EMPTY, ExecutionMode

_R = TypeVar("_R")
_P = ParamSpec("_P")


@final
class Runnable(Generic[_R]):
    __slots__: tuple[str, ...] = (
        "args",
        "exec_mode",
        "func",
        "is_async",
        "kwargs",
    )

    def __init__(
        self,
        f: Callable[_P, _R],
        /,
        exec_mode: ExecutionMode,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> None:
        self.func = f
        self.args = args
        self.kwargs = kwargs
        self.is_async = inspect.iscoroutinefunction(f)

        if self.is_async:
            if exec_mode in (ExecutionMode.PROCESS, ExecutionMode.THREAD):
                msg = (
                    "Async functions are always done in the main loop."
                    " This mode (PROCESS/THREAD) is not used."
                )
                warnings.warn(msg, category=RuntimeWarning, stacklevel=3)
            self.exec_mode = ExecutionMode.MAIN
        elif exec_mode is EMPTY:
            self.exec_mode = ExecutionMode.THREAD
        else:
            self.exec_mode = exec_mode

    def __call__(self) -> _R:
        return self.func(*self.args, **self.kwargs)


def iscoroutinerunnable(
    runnable: Runnable[_R],
) -> TypeGuard[Runnable[Awaitable[_R]]]:
    return runnable.is_async
