"""Serializers module for Jobify.

This module provides serialization utilities for task data and results.
Available serializers implement the `Serializer` protocol.

Classes:
    Serializer: Abstract base protocol defining serializer interface
    JSONSerializer: Standard JSON serializer
    ExtendedJSONSerializer: JSON serializer supporting extended types
    CBORSerializer: CBOR binary format serializer
    MsgpackSerializer: Msgpack binary format serializer
    OrjsonSerializer: High-performance JSON serializer (using `orjson`)
    UnsafePickleSerializer: Pickle-based serializer (use with caution)

Protocol Interface:
    dumpb(value: Any) -> bytes: Serialize object to bytes
    loadb(value: bytes) -> Any: Deserialize bytes to object

Security Notes:
    - JSON, CBOR, Msgpack, Orjson: Generally safe for data exchange.
    - UnsafePickleSerializer: UNSAFE for untrusted data - allows arbitrary code execution.

"""  # noqa: E501

from jobify._internal.serializers.base import Serializer
from jobify._internal.serializers.json import JSONSerializer
from jobify._internal.serializers.json_extended import ExtendedJSONSerializer
from jobify._internal.serializers.pickle_unsafe import UnsafePickleSerializer
from jobify.serializers.cbor import CBORSerializer
from jobify.serializers.msgpack import MsgpackSerializer
from jobify.serializers.orjson import OrjsonSerializer

__all__ = (
    "CBORSerializer",
    "ExtendedJSONSerializer",
    "JSONSerializer",
    "MsgpackSerializer",
    "OrjsonSerializer",
    "Serializer",
    "UnsafePickleSerializer",
)
