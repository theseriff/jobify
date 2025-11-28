from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any, TypeAlias, TypeVar

from jobber._internal.context import JobContext

AppType = TypeVar("AppType")

StatelessLifespan: TypeAlias = Callable[
    [AppType],
    AbstractAsyncContextManager[None],
]
StatefulLifespan: TypeAlias = Callable[
    [AppType], AbstractAsyncContextManager[Mapping[str, Any]]
]
Lifespan: TypeAlias = StatelessLifespan[AppType] | StatefulLifespan[AppType]

ExceptionHandler = Callable[[JobContext, Exception], Awaitable[None] | None]
ExceptionHandlers = dict[type[Exception], ExceptionHandler]
MappingExceptionHandlers = Mapping[type[Exception], ExceptionHandler]
