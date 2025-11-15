"""Core scheduling components for the iojobs library.

This module provides the basic classes for job scheduling and management.
It exposes the main scheduler interface and job planning components that
form the basis of the iojobs asynchronous job scheduling system.
"""

from importlib.metadata import version as get_version

from iojobs._internal.constants import ExecutionMode, JobStatus
from iojobs._internal.datastructures import State
from iojobs._internal.runner.job import Job
from iojobs._internal.runner.runner import JobRunner
from iojobs._internal.scheduler import JobScheduler

__version__ = get_version("iojobs")
__all__ = (
    "ExecutionMode",
    "Job",
    "JobRunner",
    "JobScheduler",
    "JobStatus",
    "State",
)
