"""Core scheduling components for the jobber library.

This module provides the basic classes for job scheduling and management.
It exposes the main scheduler interface and job planning components that
form the basis of the jobber asynchronous job scheduling system.
"""

from importlib.metadata import version as get_version

from jobber._internal.common.constants import ExecutionMode, JobStatus
from jobber._internal.common.datastructures import RequestState, State
from jobber._internal.context import JobContext
from jobber._internal.injection import INJECT
from jobber._internal.jobber import Jobber
from jobber._internal.runner.job import Job
from jobber._internal.runner.runnable import Runnable
from jobber._internal.runner.scheduler import ScheduleBuilder

__version__ = get_version("jobber")
__all__ = (
    "INJECT",
    "ExecutionMode",
    "Job",
    "JobContext",
    "JobStatus",
    "Jobber",
    "RequestState",
    "Runnable",
    "ScheduleBuilder",
    "State",
)
