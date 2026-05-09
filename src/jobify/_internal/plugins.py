from abc import ABC
from typing import Generic

from jobify._internal.common.types import AppType


class Plugin(ABC, Generic[AppType]):
    async def startup(self, app: AppType) -> None: ...
    async def shutdown(self) -> None: ...
