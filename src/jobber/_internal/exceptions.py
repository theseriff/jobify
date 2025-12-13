from typing import NoReturn


class BaseJobberError(Exception):
    pass


class JobNotCompletedError(BaseJobberError):
    """Raised when trying to access result of incomplete job."""

    def __init__(
        self,
        message: str = (
            "Job result is not ready yet, "
            "please use .wait() and then you can use .result"
        ),
    ) -> None:
        super().__init__(message)


class JobFailedError(BaseJobberError):
    def __init__(self, job_id: str, reason: str) -> None:
        self.job_id: str = job_id
        self.reason: str = reason
        message = f"job_id: {job_id}, failed_reason: {reason}"
        super().__init__(message)


class NegativeDelayError(BaseJobberError):
    """Exception raised when negative delay_seconds is provided."""

    def __init__(
        self,
        delay_seconds: float,
        message: str = (
            "Negative delay_seconds ({delay_seconds}) is not supported. "
            "Please provide non-negative values."
        ),
    ) -> None:
        super().__init__(message.format(delay_seconds=delay_seconds))
        self.delay_seconds: float = delay_seconds


class JobTimeoutError(BaseJobberError):
    """Raised when job execution exceeds the configured timeout."""

    def __init__(self, job_id: str, timeout: float) -> None:
        self.job_id: str = job_id
        self.timeout: float = timeout

        message = (
            f"job_id: {job_id} exceeded timeout of {timeout} seconds. "
            "Job execution was interrupted."
        )
        super().__init__(message)


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

        message = (
            f"Cannot perform operation '{operation}'.\n"
            f"  Reason: {reason}\n"
            f"  Resolution: {solution}"
        )
        super().__init__(message)


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
