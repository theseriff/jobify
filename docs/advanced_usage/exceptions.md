# Exceptions

This page describes the common errors you might encounter while using Jobify.

## Job Execution Errors

These errors are related to the execution of individual jobs and are typically raised when you call `job.result()`.

### `JobFailedError`

Raised when a job fails due to an exception within the task function. It wraps the original exception.

- **Attributes**:
    - `job_id`: The ID of the failed job.
    - `reason`: A string representation of the original exception.

### `JobTimeoutError`

Raised when a job's execution exceeds the configured `timeout`.

- **Attributes**:
    - `job_id`: The ID of the timed-out job.
    - `timeout`: The timeout value in seconds.

### `JobNotCompletedError`

Raised when you attempt to call `job.result()` before the job has finished executing (i.e., its status is not `SUCCESS`, `FAILED`, or `TIMEOUT`).

## Scheduling Exceptions

### `DuplicateJobError`

Raised when you attempt to schedule a job with an ID that is already in use by another active job.

- **Solution**: Use `replace=True` when scheduling if you want to update the existing job.

## Application State Exceptions

### `ApplicationStateError`

Raised when an operation is performed while the application is in an invalid state (e.g., trying to configure the app after it has already started).

#### Common Scenarios:

- **Registering a task after startup**: All tasks must be registered (via `@app.task` or `app.include_router()`) before calling `async with app:` or `await app.startup()`.
- **Scheduling a task before startup**: You cannot schedule a task (using `.at()`, `.delay()`, or `.cron()`) before the application has started.

## Routing Exceptions

### `RouteAlreadyRegisteredError`

Raised when you try to register a task with a name that has already been taken within the same router or application.
