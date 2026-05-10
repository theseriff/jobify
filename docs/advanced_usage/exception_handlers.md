# Exception Handlers

Exception handlers provide custom logic for dealing with errors during task execution. They are essential for logging, monitoring, and implementing custom recovery strategies.

<div class="grid cards" markdown>

- :material-layers-outline:{ .lg .middle } **Hierarchical Priority**

    ***

    Handlers follow a "most-specific-first" rule:
    **Task** > **Router** > **Global**.

- :material-refresh:{ .lg .middle } **Retry Control**

    ***

    Reraise to trigger retries, or return a value to recover and mark the job as `SUCCESS`.

- :material-alert-octagon-outline:{ .lg .middle } **Fatal Failures**

    ***

    Raise `NoResultError` to abort all future retries and fail the job immediately.

- :material-vector-arrange-below:{ .lg .middle } **Scoped Logic**

    ***

    Define handlers at Task, Router, or Global levels for fine-grained control.

</div>

## How It Works

Jobify looks for the most specific exception handler based on the exception type (or its parent class). If a handler is found at the task level, it executes, and parent levels are ignored.

### Handler Signature

A handler is a sync or async callable taking exactly two arguments:

- :material-alert-circle-outline: **`exc`**: The exception instance raised by the task.
- :material-briefcase-variant-outline: **`context`**: The `JobContext` of the current execution.

```python
async def my_handler(exc: Exception, context: JobContext) -> None:
    print(f"Job {context.job.id} failed: {exc}")
```

## Configuration Levels

=== "Global Level"

    Applied to every task in the `Jobify` application.

    ```python
    app = Jobify(
        exception_handlers={
            TypeError: global_type_error_handler
        }
    )
    ```

=== "Router Level"

    Applied to all tasks within a specific `JobRouter`.

    ```python
    router = JobRouter(
        exception_handlers={
            ValueError: router_value_error_handler
        }
    )
    ```

=== "Task Level"

    Specific to a single `@app.task`. Overrides both Router and Global levels.

    ```python
    @app.task(
        exception_handlers={
            TimeoutError: task_timeout_handler
        }
    )
    async def my_task(): ...
    ```

## Execution Behavior

How your handler exits determines the final state of the job and whether retries occur.

=== "1. Trigger Retries"

    To allow `RetryMiddleware` to catch the error and retry the task, you **must** re-raise the exception.

    ```python
    async def my_handler(exc: Exception, context: JobContext):
        log.error("Retrying...")
        raise exc  # Re-raise to trigger retry logic
    ```

=== "2. Recovery (Success)"

    If you return a value (or simply exit), the job is marked as `SUCCESS`. The returned value becomes the `job.result()`.

    ```python
    async def recovery_handler(exc, ctx) -> str:
        return "fallback_value"  # Job status: SUCCESS
    ```

=== "3. Abort (No Retries)"

    To stop all retries and fail immediately, raise `NoResultError`.

    ```python
    from jobify.exceptions import NoResultError

    async def fatal_handler(exc, ctx):
        raise NoResultError  # Job status: FAILED, no retries
    ```

## Hierarchical Example

!!! info "Evaluation Order"
    When `TypeError` is raised in `process_report`:
    1. Check `process_report` task handlers (Found! -> Run it).
    2. Ignore Router and Global levels.

```python
# Global
app = Jobify(exception_handlers={TypeError: handle_global})

# Router
router = JobRouter(prefix="reports", exception_handlers={TypeError: handle_router})

# Task
@router.task(exception_handlers={TypeError: handle_task})
async def process_report():
    raise TypeError("Specific error")
```
