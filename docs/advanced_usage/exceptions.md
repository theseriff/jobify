# Exceptions Reference

This page provides a reference for all common exceptions raised by Jobify.

<div class="grid cards" markdown>

- :material-run-fast:{ .lg .middle } **Execution Errors**

    ***

    Raised during task execution or when retrieving job results.

- :material-calendar-plus:{ .lg .middle } **Scheduling Errors**

    ***

    Raised when a job cannot be registered or updated.

- :material-database-alert-outline:{ .lg .middle } **State Errors**

    ***

    Raised when operations are performed in an invalid application state.

- :material-map-marker-path:{ .lg .middle } **Routing Errors**

    ***

    Raised during task registration and router inclusion.

</div>

## Execution Exceptions

These are raised when interacting with a `Job` object, typically via `job.result()` or `job.wait()`.

| Exception | Description | Attributes |
| :--- | :--- | :--- |
| :material-alert-circle: **`JobFailedError`** | Wrapped exception from a failed task. | `job_id`, `reason` |
| :material-timer-off: **`JobTimeoutError`** | Raised when execution exceeds `timeout`. | `job_id`, `timeout` |
| :material-progress-clock: **`JobNotCompletedError`** | `result()` called while job is still active. | `job_id` |

## Scheduling Exceptions

Raised by `.push()`, `.at()`, `.delay()`, or `.cron()` methods.

| Exception | Description | Solution |
| :--- | :--- | :--- |
| :material-content-copy: **`DuplicateJobError`** | Job ID already exists in storage. | Use `replace=True` to update. |

## Application State Exceptions

Raised when calling methods at the wrong point in the application lifecycle.

| Exception | Description | Common Scenarios |
| :--- | :--- | :--- |
| :material-state-machine: **`ApplicationStateError`** | Invalid operation for current state. | Registering tasks after startup; Scheduling before startup. |

## Routing Exceptions

Raised during the definition phase of your application.

| Exception | Description |
| :--- | :--- |
| :material-source-branch: **`RouteAlreadyRegisteredError`** | Task name conflict within a router or app. |
