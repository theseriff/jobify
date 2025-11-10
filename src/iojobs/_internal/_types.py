from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any

StatelessLifespan = Callable[[], AbstractAsyncContextManager[None]]
StatefulLifespan = Callable[
    [],
    AbstractAsyncContextManager[Mapping[str, Any]],  # pyright: ignore[reportExplicitAny]
]
Lifespan = StatelessLifespan | StatefulLifespan
