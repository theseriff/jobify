import json

from typing_extensions import override

from jobber._internal.serializers.base import JSONCompat, Serializer


class JSONSerializer(Serializer):
    @override
    def dumpb(self, data: JSONCompat) -> bytes:
        return json.dumps(data).encode("utf-8")

    @override
    def loadb(self, data: bytes) -> JSONCompat:
        r: JSONCompat = json.loads(data)
        return r
