# pyright: reportImportCycles=false
import asyncio
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar

if TYPE_CHECKING:
    from jobify._internal.context import JobContext

AppType = TypeVar("AppType")

StatelessLifespan: TypeAlias = Callable[
    [AppType],
    AbstractAsyncContextManager[None],
]
StatefulLifespan: TypeAlias = Callable[
    [AppType],
    AbstractAsyncContextManager[Mapping[str, Any]],
]
Lifespan: TypeAlias = StatelessLifespan[AppType] | StatefulLifespan[AppType]
LoopFactory: TypeAlias = Callable[[], asyncio.AbstractEventLoop]


ExceptionHandler: TypeAlias = Callable[[Exception, "JobContext"], Any]
ExceptionHandlers: TypeAlias = dict[type[Exception], ExceptionHandler]
MappingExceptionHandlers: TypeAlias = Mapping[
    type[Exception], ExceptionHandler
]
