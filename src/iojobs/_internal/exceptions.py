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


class JobFailedError(IOJobsBaseError):
    def __init__(self, job_id: str, reason: str) -> None:
        self.job_id: str = job_id
        self.reason: str = reason
        message = f"job_id: {job_id}, failed_reason: {reason}"
        super().__init__(message)


class NegativeDelayError(IOJobsBaseError):
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


class JobNotInitializedError(IOJobsBaseError):
    """Raised when job components are accessed before initialization."""

    def __init__(
        self,
        message: str = (
            "Job is not initialized. "
            "Ensure the job has been properly created and configured "
            "before accessing its properties."
        ),
    ) -> None:
        super().__init__(message)
