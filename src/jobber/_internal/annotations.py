# pyright: reportExplicitAny=false
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any, TypeAlias, TypeVar

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

AnyDict: TypeAlias = dict[str, Any]
