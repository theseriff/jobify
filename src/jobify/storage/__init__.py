"""Package provides various storage solutions for Jobify."""

from jobify._internal.storage.base import Storage
from jobify._internal.storage.sqlite import SQLiteStorage

__all__ = ("SQLiteStorage", "Storage")
