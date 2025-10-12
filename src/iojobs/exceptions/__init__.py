"""Custom exceptions for the iojobs library.

This module defines specific exceptions that the iojobs scheduling
system can raise. These exceptions provide more detailed information
about errors and guidance on how to handle common scheduling scenarios.
"""

from iojobs._internal.exceptions import (
    IOJobsBaseError,
    JobFailedError,
    JobNotCompletedError,
    JobNotInitializedError,
    NegativeDelayError,
)

__all__ = (
    "IOJobsBaseError",
    "JobFailedError",
    "JobNotCompletedError",
    "JobNotInitializedError",
    "NegativeDelayError",
)
