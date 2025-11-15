"""Middleware system for job execution pipeline.

This module provides a basic interface for creating middleware that can
intercept and process jobs before they reach their final destination.
Middleware can be combined together to create a processing chain,
where each piece of middleware can:

- Execute code before the job is handled
- Pass control to the next middleware in the pipeline
- Execute code after the job has been handled
- Modify the state or the result
- Break out of the chain by skipping the `call_next()` method
"""

from iojobs._internal.middleware.base import BaseMiddleware, CallNextChain

__all__ = ("BaseMiddleware", "CallNextChain")
