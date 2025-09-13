class TaskaioBaseError(Exception):
    pass


class TaskNotCompletedError(TaskaioBaseError):
    """Raised when trying to access result of incomplete task."""

    def __init__(
        self,
        message: str = (
            "Task result is not ready yet, "
            "please use .wait() and then you can use .result"
        ),
    ) -> None:
        super().__init__(message)


class LambdaNotAllowedError(TaskaioBaseError):
    """Exception raised when lambda function is used as callback."""

    def __init__(
        self,
        message: str = (
            "Lambda functions cannot be used as callbacks. "
            "Use named functions or methods instead."
        ),
    ) -> None:
        super().__init__(message)


class NegativeDelayError(TaskaioBaseError):
    """Exception raised when negative delay_seconds is provided."""

    def __init__(
        self,
        delay_seconds: float,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = (
                f"Negative delay_seconds ({delay_seconds}) is not supported. "
                "Please provide non-negative values."
            )
        super().__init__(message)
        self.delay_seconds: float = delay_seconds
