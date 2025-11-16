"""Core scheduling components for the jobber library.

This module provides the basic classes for job scheduling and management.
It exposes the main scheduler interface and job planning components that
form the basis of the jobber asynchronous job scheduling system.
"""

from importlib.metadata import version as get_version

from jobber._internal.constants import ExecutionMode, JobStatus
from jobber._internal.datastructures import State
from jobber._internal.jobber import Jobber
from jobber._internal.runner.job import Job
from jobber._internal.runner.runner import JobRunner

__version__ = get_version("jobber")
__all__ = (
    "ExecutionMode",
    "Job",
    "JobRunner",
    "JobStatus",
    "Jobber",
    "State",
)
