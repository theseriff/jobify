import inspect
from collections.abc import Callable
from typing import (
    Any,
    Generic,
    ParamSpec,
    TypeAlias,
    TypeVar,
    final,
    get_origin,
    get_type_hints,
)

ReturnT = TypeVar("ReturnT")
ParamsT = ParamSpec("ParamsT")

INJECT: Any = object()
ParamName: TypeAlias = str
TypeHint: TypeAlias = Any


@final
class FuncSpec(Generic[ReturnT]):
    __slots__: tuple[str, ...] = (
        "inject_params",
        "name",
        "result_type",
        "signature",
        "type_params",
    )

    def __init__(
        self,
        *,
        name: str,
        signature: inspect.Signature,
        result_type: type[ReturnT],
        type_params: dict[ParamName, TypeHint],
        inject_params: dict[str, Any],
    ) -> None:
        self.name = name
        self.signature = signature
        self.result_type = result_type
        self.type_params = type_params
        self.inject_params = inject_params


def get_type_params(
    sig: inspect.Signature,
    hints: dict[str, Any],
) -> dict[ParamName, TypeHint]:
    return {
        arg.name: hints.get(arg.name, Any) for arg in sig.parameters.values()
    }


def get_inject_params(
    sig: inspect.Signature,
    hints: dict[str, Any],
) -> dict[str, Any]:
    inject_params: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if param.default is not INJECT:
            continue
        annotation = hints.get(name, inspect.Parameter.empty)
        if annotation is inspect.Parameter.empty:
            msg = f"Parameter {name!r} requires a type annotation for INJECT"
            raise ValueError(msg)
        inject_params[name] = get_origin(annotation) or annotation

    return inject_params


def get_result_type(hints: dict[str, Any]) -> Any:  # noqa: ANN401
    return hints.get("return", Any)


def make_func_spec(func: Callable[ParamsT, ReturnT]) -> FuncSpec[ReturnT]:
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    return FuncSpec(
        name=func.__name__,
        result_type=get_result_type(hints),
        type_params=get_type_params(sig, hints),
        inject_params=get_inject_params(sig, hints),
        signature=sig,
    )
