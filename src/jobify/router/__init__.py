"""Module with all the main stuff for organizing and managing tasks in Jobify.

Includes JobRouter for grouping tasks into logical units, and RootRoute
and NodeRoute classes as basis for task execution and hierarchical routing.
"""

from jobify._internal.router.node import NodeRoute
from jobify._internal.router.node import NodeRouter as JobRouter
from jobify._internal.router.root import RootRoute

__all__ = (
    "JobRouter",
    "NodeRoute",
    "RootRoute",
)
