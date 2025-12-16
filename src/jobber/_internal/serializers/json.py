import json

from jobber._internal.serializers.base import (
    JobsSerializer,
    SerializableTypes,
    json_extended_decoder,
    json_extended_encoder,
)


class ExtendedEncoder(json.JSONEncoder):
    def encode(self, o: SerializableTypes) -> str:
        json_compat = json_extended_encoder(o)
        return super().encode(json_compat)


class JSONSerializer(JobsSerializer):
    def dumpb(self, data: SerializableTypes) -> bytes:
        return json.dumps(data, cls=ExtendedEncoder).encode("utf-8")

    def loadb(self, data: bytes) -> SerializableTypes:
        decoded: SerializableTypes = json.loads(
            data,
            object_hook=json_extended_decoder,
        )
        return decoded
