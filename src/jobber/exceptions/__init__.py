"""Custom exceptions for the jobber library.

This module defines specific exceptions that the jobber scheduling
system can raise. These exceptions provide more detailed information
about errors and guidance on how to handle common scheduling scenarios.
"""

from jobber._internal.exceptions import (
    BaseJobberError,
    JobFailedError,
    JobNotCompletedError,
    JobSkippedError,
    NegativeDelayError,
)

__all__ = (
    "BaseJobberError",
    "JobFailedError",
    "JobNotCompletedError",
    "JobSkippedError",
    "NegativeDelayError",
)
