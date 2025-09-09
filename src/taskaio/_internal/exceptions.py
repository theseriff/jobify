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


class TimerHandlerUninitializedError(TaskaioBaseError):
    """Raised when attempting to use an uninitialized timer handler.

    This occurs when accessing the timer handler before the task has been
    scheduled. The timer handler is lazily initialized during task scheduling.
    """

    def __init__(
        self,
        message: str = (
            "Timer handler is not initialized - "
            "schedule the task first with at(..) or delay(..)"
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
