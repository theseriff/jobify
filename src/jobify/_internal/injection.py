import inspect
from typing import Any, TypeVar, get_origin, get_type_hints

from jobify._internal.context import JobContext

ReturnT = TypeVar("ReturnT")


def _build_context_mapping(context_cls: type[JobContext]) -> dict[type, str]:
    type_hints = get_type_hints(context_cls)
    return {
        get_origin(field_type) or field_type: field_name
        for field_name, field_type in type_hints.items()
    }


INJECT: Any = object()
CONTEXT_TYPE_MAP = _build_context_mapping(JobContext)


def inject_context(context: JobContext) -> None:
    runnable = context.runnable
    arguments = runnable.bound.arguments
    for name, param in runnable.bound.signature.parameters.items():
        if param.default is not INJECT:
            continue

        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            msg = f"Parameter {name} requires a type annotation for INJECT"
            raise ValueError(msg)

        tp = get_origin(annotation) or annotation
        if tp is JobContext:
            val = context
        elif field_name := CONTEXT_TYPE_MAP.get(tp):
            val = getattr(context, field_name)
        else:
            msg = (
                f"Unknown type for injection: {tp}. "
                f"Available types: {list(CONTEXT_TYPE_MAP.keys())}"
            )
            raise ValueError(msg)
        arguments[name] = val
