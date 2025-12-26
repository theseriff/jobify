from __future__ import annotations

from typing import Any

from typing_extensions import override

from jobber._internal.typeadapter.base import Dumper, Loader


class DummyLoader(Loader):
    @override
    def load(self, data: Any, tp: Any, /) -> Any:
        return data


class DummyDumper(Dumper):
    @override
    def dump(self, data: Any, tp: Any, /) -> Any:
        return data
