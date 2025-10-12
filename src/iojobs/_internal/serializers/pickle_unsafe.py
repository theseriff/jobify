# ruff: noqa: ANN401, ERA001
# pyright: reportExplicitAny=false

import pickle  # nosec B403
from typing import Any

from iojobs._internal.serializers.abc import JobsSerializer


class UnsafePickleSerializer(JobsSerializer):
    def dumpb(self, value: Any) -> bytes:
        # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
        return pickle.dumps(value)

    def loadb(self, value: bytes) -> Any:
        # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
        return pickle.loads(value)  # noqa: S301 # nosec B301
