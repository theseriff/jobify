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


class TaskNotInitializedError(TaskaioBaseError):
    """Raised when task components are accessed before initialization."""

    def __init__(
        self,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = (
                "TaskInfo is not initialized. "
                "Ensure the task has been properly created and configured "
                "before accessing its properties."
            )
        super().__init__(message)


class CronParseError(TaskaioBaseError):
    """Exception raised when cron expression parsing fails.

    This exception is raised when an invalid cron expression is provided
    to a scheduled task. Cron expressions must follow the standard format
    and contain valid values for each time field.

    Examples of invalid expressions that would raise this error:
    - "*/15 * * *" (too few fields)
    - "60 * * * *" (minutes out of range 0-59)
    - "*/10 * 32 * *" (day of month out of range 1-31)
    - "0 0 * JAN-MAR *" (invalid month names without proper support)
    - "*/5 * * * * *" (too many fields)

    Attributes:
        expression: The cron expression that failed to parse (if available)
        message: Detailed explanation of the parsing error

    """

    def __init__(
        self,
        expression: str | None = None,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = "Failed to parse cron expression"
            if expression:
                message += f": {expression}"

        super().__init__(message)
        self.expression: str | None = expression
