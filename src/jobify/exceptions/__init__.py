"""Custom exceptions for the jobify framework.

This module defines specific exceptions that the jobify scheduling
system can raise. These exceptions provide more detailed information
about errors and guidance on how to handle common scheduling scenarios.
"""

from jobify._internal.exceptions import (
    ApplicationStateError,
    BaseJobifyError,
    DuplicateJobError,
    JobFailedError,
    JobNotCompletedError,
    JobTimeoutError,
    RouteAlreadyRegisteredError,
)

__all__ = (
    "ApplicationStateError",
    "BaseJobifyError",
    "DuplicateJobError",
    "JobFailedError",
    "JobNotCompletedError",
    "JobTimeoutError",
    "RouteAlreadyRegisteredError",
)
