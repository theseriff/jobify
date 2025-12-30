import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, ParamSpec, TypeAlias, TypeVar, get_type_hints

ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")

ParamName: TypeAlias = str
TypeHint: TypeAlias = Any


@dataclass(slots=True, kw_only=True)
class FuncSpec(Generic[ReturnT]):
    name: str
    signature: inspect.Signature
    params_type: dict[ParamName, TypeHint]
    result_type: type[ReturnT]


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
