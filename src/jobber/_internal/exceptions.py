from typing import NoReturn


class BaseJobberError(Exception):
    pass


class JobNotCompletedError(BaseJobberError):
    """Raised when trying to access result of incomplete job."""

    def __init__(
        self,
        msg: str = (
            "Job result is not ready yet, "
            "please use .wait() and then you can use .result"
        ),
    ) -> None:
        super().__init__(msg)


class JobFailedError(BaseJobberError):
    def __init__(self, job_id: str, reason: str) -> None:
        self.job_id: str = job_id
        self.reason: str = reason
        super().__init__(f"job_id: {job_id}, failed_reason: {reason}")


class JobTimeoutError(BaseJobberError):
    """Raised when job execution exceeds the configured timeout."""

    def __init__(self, job_id: str, timeout: float) -> None:
        self.job_id: str = job_id
        self.timeout: float = timeout

        msg = (
            f"job_id: {job_id} exceeded timeout of {timeout} seconds. "
            "Job execution was interrupted."
        )
        super().__init__(msg)


class DuplicateJobError(RuntimeError):
    """Raised when a job is scheduled with an ID that is already in use."""

    def __init__(self, job_id: str) -> None:
        self.job_id: str = job_id
        super().__init__(f"Job with ID {job_id!r} is already scheduled.")


class RouteAlreadyRegisteredError(BaseJobberError):
    """A route with this name has already been registered."""

    def __init__(self, name: str) -> None:
        msg = f"A route with the name {name!r} has already been registered."
        super().__init__(msg)


class ApplicationStateError(BaseJobberError):
    """Raised when app is in wrong state for the requested operation."""

    def __init__(
        self,
        *,
        operation: str,
        reason: str,
        solution: str,
    ) -> None:
        self.operation: str = operation
        self.reason: str = reason
        self.solution: str = solution

        msg = (
            f"Cannot perform operation '{operation}'.\n"
            f"  Reason: {reason}\n"
            f"  Resolution: {solution}"
        )
        super().__init__(msg)


def raise_app_not_started_error(operation: str) -> NoReturn:
    raise ApplicationStateError(
        operation=operation,
        reason="The Jobber application is not started.",
        solution=(
            "Ensure you are calling this method inside an 'async with jobber:'"
            "block or after calling 'await jobber.startup()'."
        ),
    )


def raise_app_already_started_error(operation: str) -> NoReturn:
    raise ApplicationStateError(
        operation=operation,
        reason="The Jobber app's already running and configuration is frozen.",
        solution=(
            "Configuration methods (register, add_middleware, etc.)"
            "must be called BEFORE the application starts."
            "Move this call outside/before the 'async with jobber:' block."
        ),
    )
