"""Core scheduling components for the taskaio library.

This module provides the basic classes for task scheduling and management.
It exposes the main scheduler interface and task planning components that
form the basis of the taskaio asynchronous task scheduling system.
"""

from importlib.metadata import version as get_version

from taskaio._internal.scheduler import TaskScheduler
from taskaio._internal.task_executor import TaskExecutor, TaskInfo

__version__ = get_version("taskaio")
__all__ = (
    "TaskExecutor",
    "TaskInfo",
    "TaskScheduler",
)
