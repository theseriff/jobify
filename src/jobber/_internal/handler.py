from collections.abc import Callable
from typing import Generic, ParamSpec, TypeVar, final

from jobber._internal.constants import EMPTY

_ReturnType = TypeVar("_ReturnType")
_FuncParams = ParamSpec("_FuncParams")


@final
class Handler(Generic[_FuncParams, _ReturnType]):
    def __init__(
        self,
        job_name: str,
        original_func: Callable[_FuncParams, _ReturnType],
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> None:
        self.job_id = EMPTY
        self.job_name = job_name
        self.original_func = original_func
        self.original_args = args
        self.original_kwargs = kwargs

    def __call__(self) -> _ReturnType:
        return self.original_func(*self.original_args, **self.original_kwargs)
