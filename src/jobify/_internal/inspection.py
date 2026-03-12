import inspect
from collections.abc import Callable
from typing import (
    Any,
    Generic,
    ParamSpec,
    TypeAlias,
    TypeVar,
    final,
    get_type_hints,
)

ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")

ParamName: TypeAlias = str
TypeHint: TypeAlias = Any


@final
class FuncSpec(Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "name",
        "params_type",
        "result_type",
        "signature",
    )

    def __init__(
        self,
        *,
        name: str,
        signature: inspect.Signature,
        params_type: dict[ParamName, TypeHint],
        result_type: type[ReturnT],
    ) -> None:
        self.name = name
        self.signature = signature
        self.params_type = params_type
        self.result_type = result_type


def get_params_type(
    sig: inspect.Signature,
    hints: dict[str, Any],
) -> dict[ParamName, TypeHint]:
    return {
        arg.name: hints.get(arg.name, Any) for arg in sig.parameters.values()
    }


def get_result_type(hints: dict[str, Any]) -> Any:  # noqa: ANN401
    return hints.get("return", Any)


def make_func_spec(func: Callable[ParamsT, ReturnT]) -> FuncSpec[ReturnT]:
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    return FuncSpec(
        name=func.__name__,
        params_type=get_params_type(sig, hints),
        result_type=get_result_type(hints),
        signature=sig,
    )
