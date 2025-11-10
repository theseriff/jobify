# ruff: noqa: ERA001
# pyright: reportExplicitAny=false

import pickle  # nosec B403

from iojobs._internal.serializers.abc import JobsSerializer, SerializableTypes


class UnsafePickleSerializer(JobsSerializer):
    def dumpb(self, data: SerializableTypes) -> bytes:
        # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
        return pickle.dumps(data)

    def loadb(self, data: bytes) -> SerializableTypes:
        # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
        decoded: SerializableTypes = pickle.loads(data)  # noqa: S301 # nosec B301
        return decoded
