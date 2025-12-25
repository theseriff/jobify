# ruff: noqa: ERA001
# pyright: reportExplicitAny=false

import pickle  # nosec B403
from typing import Any

from typing_extensions import override

from jobber._internal.serializers.base import Serializer


class UnsafePickleSerializer(Serializer):
    @override
    def dumpb(self, data: Any) -> bytes:
        # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
        return pickle.dumps(data)

    @override
    def loadb(self, data: bytes) -> Any:
        # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
        return pickle.loads(data)  # noqa: S301 # nosec B301
