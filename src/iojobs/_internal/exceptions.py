class IOJobsBaseError(Exception):
    pass


class JobNotCompletedError(IOJobsBaseError):
    """Raised when trying to access result of incomplete job."""

    def __init__(
        self,
        message: str = (
            "Job result is not ready yet, "
            "please use .wait() and then you can use .result"
        ),
    ) -> None:
        super().__init__(message)


class NegativeDelayError(IOJobsBaseError):
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


class JobNotInitializedError(IOJobsBaseError):
    """Raised when job components are accessed before initialization."""

    def __init__(
        self,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = (
                "JobInfo is not initialized. "
                "Ensure the job has been properly created and configured "
                "before accessing its properties."
            )
        super().__init__(message)


class ConcurrentExecutionError(IOJobsBaseError):
    """Raised when both thread and process execution modes are specified.

    This exception is raised when a job is configured to execute both
    in a separate thread and a separate process simultaneously, which
    creates ambiguous execution behavior.

    Jobs must be configured for one of the following:
    - Default execution (main thread)
    - Thread execution (to_thread=True)
    - Process execution (to_process=True)

    But not multiple modes at the same time.
    """

    def __init__(
        self,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = (
                "Cannot execute jobs both in thread and process simultaneously. "  # noqa: E501
                "Please specify only one execution mode: either to_thread=True "  # noqa: E501
                "or to_process=True, but not both."
            )
        super().__init__(message)
