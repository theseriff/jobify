"""Serializers module for IOJobs.

This module provides serialization utilities for task data and results.
Available serializers implement the IOJobsSerializer protocol.

Classes:
    IOJobsSerializer: Abstract base protocol defining serializer interface
    AstLiteralSerializer: Safe serializer using AST literal evaluation
    UnsafePickleSerializer: Pickle-based serializer (use with caution)

Protocol Interface:
    dumpb(value: Any) -> bytes: Serialize object to bytes
    loadb(value: bytes) -> Any: Deserialize bytes to object

Security Notes:
    - AstLiteralSerializer: Safe for untrusted data, but limited to basic Python literals
    - UnsafePickleSerializer: UNSAFE for untrusted data - allows arbitrary code execution

Examples:
    >>> from iojobs.serializers import (
    ...     AstLiteralSerializer,
    ...     UnsafePickleSerializer,
    ... )
    >>> # Safe serialization for basic data types
    >>> safe_serializer = AstLiteralSerializer()
    >>> data = safe_serializer.dumpb({"key": "value", "number": 42})
    >>> obj = safe_serializer.loadb(data)
    >>> # Unsafe but flexible serialization (use only with trusted data)
    >>> unsafe_serializer = UnsafePickleSerializer()
    >>> data = unsafe_serializer.dumpb(complex_object)
    >>> obj = unsafe_serializer.loadb(data)

"""  # noqa: E501

from iojobs._internal.serializers.abc import JobsSerializer, SerializableTypes
from iojobs._internal.serializers.json import JSONSerializer
from iojobs._internal.serializers.pickle_unsafe import UnsafePickleSerializer

__all__ = (
    "JSONSerializer",
    "JobsSerializer",
    "SerializableTypes",
    "UnsafePickleSerializer",
)
