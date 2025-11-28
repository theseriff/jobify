import inspect
from typing import Any, TypeVar, get_origin, get_type_hints

from jobber._internal.context import JobContext
from jobber._internal.runner.runnable import Runnable

_R = TypeVar("_R")


class _MarkerInject:
    pass


INJECT: Any = _MarkerInject()


def _build_context_mapping(context_cls: type[JobContext]) -> dict[type, str]:
    type_hints = get_type_hints(context_cls)
    return {
        get_origin(field_type) or field_type: field_name
        for field_name, field_type in type_hints.items()
    }


CONTEXT_TYPE_MAP = _build_context_mapping(JobContext)


def inject_context(runnable: Runnable[_R], context: JobContext) -> None:
    sig = inspect.signature(runnable.func)
    for name, param in sig.parameters.items():
        if param.default is not INJECT:
            continue
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            msg = f"Parameter {name} requires a type annotation for INJECT"
            raise ValueError(msg)

        target_type = get_origin(annotation) or annotation
        if target_type is JobContext:
            val = context
        elif field_name := CONTEXT_TYPE_MAP.get(target_type):
            val = getattr(context, field_name)
        else:
            msg = (
                f"Unknown type for injection: {target_type}. "
                f"Available types: {list(CONTEXT_TYPE_MAP.keys())}"
            )
            raise ValueError(msg)
        runnable.kwargs[name] = val
