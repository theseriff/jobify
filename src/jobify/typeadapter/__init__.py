"""Type adaptation and serialization utilities.

This module provides base classes and interfaces for converting Python types
to serializable formats and back. It serves as the foundation for type
adaptation, leveraging implementations from pydantic and adaptix.

The module exports the main type adaptation interfaces:
- Dumper: Base class for serializing Python objects to JSON-compatible types
- Loader: Base class for deserializing JSON-compatible types to Python objects
"""

from jobify._internal.typeadapter.base import Dumper, Loader

__all__ = ("Dumper", "Loader")
