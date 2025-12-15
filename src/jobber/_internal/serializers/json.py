import base64
import json
from typing import Any, TypeAlias, cast

from jobber._internal.serializers.base import JobsSerializer, SerializableTypes

_JsonCompat: TypeAlias = (
    dict[str, "_JsonCompat"]
    | list["_JsonCompat"]
    | str
    | int
    | float
    | bool
    | None
)


class ExtendedEncoder(json.JSONEncoder):
    def encode(self, o: SerializableTypes) -> str:
        json_compat = self._transform(o)
        return super().encode(json_compat)

    def _transform(self, o: SerializableTypes) -> _JsonCompat:
        if isinstance(o, bytes):
            return {"__bytes__": base64.b64encode(o).decode("utf-8")}
        if isinstance(o, tuple):
            return {"__tuple__": [self._transform(item) for item in o]}
        if isinstance(o, set):
            return {"__set__": [self._transform(item) for item in o]}
        if isinstance(o, list):
            return [self._transform(item) for item in o]
        if isinstance(o, dict):
            return {k: self._transform(v) for k, v in o.items()}
        return o


def extended_decoder(dct: dict[str, Any]) -> SerializableTypes:
    if "__bytes__" in dct:
        return base64.b64decode(dct["__bytes__"])
    if "__tuple__" in dct:
        return tuple(dct["__tuple__"])
    if "__set__" in dct:
        return set(dct["__set__"])
    return dct


class JSONSerializer(JobsSerializer):
    def dumpb(self, data: SerializableTypes) -> bytes:
        return json.dumps(data, cls=ExtendedEncoder).encode("utf-8")

    def loadb(self, data: bytes) -> SerializableTypes:
        decoded = json.loads(data, object_hook=extended_decoder)
        return cast("SerializableTypes", decoded)
