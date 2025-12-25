"""Serializers module for Jobber.

This module provides serialization utilities for task data and results.
Available serializers implement the JobsSerializer protocol.

Classes:
    obsSerializer: Abstract base protocol defining serializer interface
    AstLiteralSerializer: Safe serializer using AST literal evaluation
    UnsafePickleSerializer: Pickle-based serializer (use with caution)

Protocol Interface:
    dumpb(value: Any) -> bytes: Serialize object to bytes
    loadb(value: bytes) -> Any: Deserialize bytes to object

Security Notes:
    - AstLiteralSerializer: Safe for untrusted data, but limited to basic Python literals
    - UnsafePickleSerializer: UNSAFE for untrusted data - allows arbitrary code execution

"""  # noqa: E501

from jobber._internal.serializers.base import Serializer
from jobber._internal.serializers.json import JSONSerializer
from jobber._internal.serializers.json_extended import ExtendedJSONSerializer
from jobber._internal.serializers.pickle_unsafe import UnsafePickleSerializer

__all__ = (
    "ExtendedJSONSerializer",
    "JSONSerializer",
    "Serializer",
    "UnsafePickleSerializer",
)
