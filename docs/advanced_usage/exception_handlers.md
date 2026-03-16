# Exception Handlers

Exception handlers allow you to define custom logic for dealing with errors that occur during the execution of a task. This can be useful for logging errors, sending notifications about them, or performing additional cleanup steps when a task fails.

## How it Works

You can define exception handlers at three different levels:

1. **Global Level (Jobify):** This is applied to all tasks in the application.
2. **Router Level (JobRouter):** This is used for all tasks within a specific router.
3. **Task Level (@app.task):** This is specific to a single task.

### Handler Priority

Jobify uses a hierarchical approach to handle exceptions. If an exception occurs, it looks for the most specific exception handler to handle it:

**Task Level** > **Router Level** > **Global Level**

If a handler for a specific exception type (or its parent class) is found at the task level, it will be executed, and handlers at the router or global levels will be ignored for that specific exception.

## Defining Handlers

An exception handler is a callable (sync or async) that takes two arguments:
- `exc`: The exception instance that was raised.
- `context`: The `JobContext` of the current job.

```python
from jobify import JobContext

async def my_handler(exc: Exception, context: JobContext) -> None:
    print(f"Job {context.job.id} failed with error: {exc}")
```

### 1. Global Level

Pass a dictionary to the `Jobify` constructor:

```python
from jobify import Jobify

app = Jobify(
    exception_handlers={
        TypeError: lambda exc, context: print("A TypeError occurred!")
    }
)
```

### 2. Router Level

Pass a dictionary to the `JobRouter` constructor:

```python
from jobify import JobRouter

router = JobRouter(
    exception_handlers={
        ValueError: lambda exc, context: print("A ValueError occurred in this router!")
    }
)
```

### 3. Task Level

Pass a dictionary to the `@app.task` decorator:

```python
@app.task(
    exception_handlers={
        TimeoutError: lambda exc, context: print("This specific task timed out!")
    }
)
async def my_task() -> None:
    ...
```

## Return Values and Re-raising

An important aspect of exception handlers is how they impact the final status of a job and its interaction with the `RetryMiddleware`.

### 1. Re-raising for Retries

If you want the job to be retried (assuming `retry` is configured in `@app.task`), your exception handler must re-raise the exception.

```python
async def my_handler(exc: Exception, context: JobContext) -> None:
    print(f"Logging error for job {context.job.id}")
    # Re-raise the exception so RetryMiddleware can catch it and retry the task
    raise exc
```

When an exception is re-raised, Jobify's internal `RetryMiddleware` will see it and, if there are remaining retry attempts, it will schedule the task for another run.

### 2. Handling without Re-raising (Recovery)

If your exception handler handles the exception and returns a value (or simply completes without raising an error), Jobify will consider the error "handled".

- The job status will be set to `SUCCESS`.
- The return value of the handler will be stored as the `job.result()`.
- No retries will be attempted by `RetryMiddleware`.

```python
async def my_recovery_handler(exc: Exception, context: JobContext) -> str:
    print(f"Recovering from error: {exc}")
    # This return value will be stored as the job's result
    return "default_value"

@app.task(exception_handlers={ValueError: my_recovery_handler})
async def my_task() -> None:
    raise ValueError("Oops!")
```

### 3. Aborting Retries with NoResultError

Sometimes, an error can be fatal and retrying a task (even if the `retry` configuration is set) would be a waste of resources.
In these cases, it is recommended to raise the `jobify.exceptions.NoResultError` exception.

- When this exception is raised, the job's status will be set to FAILED.
- The `RetryMiddleware` component will catch this exception and stop all further retries.
- No more retries will be attempted.

```python
import asyncio

from jobify import JobContext, Jobify
from jobify.exceptions import NoResultError

app = Jobify()

async def fatal_error_handler(exc: Exception, context: JobContext) -> None:
    print(f"Fatal error in job {context.job.id}: {exc}")
    # Signal that we should stop retries and fail the job immediately
    raise NoResultError

@app.task(retry=3, exception_handlers={ValueError: fatal_error_handler})
async def my_task() -> None:
    raise ValueError("Corrupted data!")

async def main() -> None:
    async with app:
        job = await my_task.push()
        await job.wait()

        print(job.status) # FAILED
        print(job.exception) # NoResultError

asyncio.run(main())
```

## Example: Hierarchical Handling

The following example demonstrates how handlers at different levels interact:

```python
import asyncio
from jobify import INJECT, JobContext, Jobify, JobRouter

# Global handler for TypeError
app = Jobify(
    exception_handlers={
        TypeError: lambda exc, ctx: print(f"Global handler: {exc}")
    }
)

# Router with its own TypeError handler
router = JobRouter(
    prefix="reports",
    exception_handlers={
        TypeError: lambda exc, ctx: print(f"Router handler: {exc}")
    }
)

# Task with its own TypeError and TimeoutError handlers
@router.task(
    exception_handlers={
        TypeError: lambda exc, ctx: print(f"Task handler: {exc}"),
        TimeoutError: lambda exc, ctx: print(f"Task timeout handler: {exc}"),
    }
)
async def process_report(context: JobContext = INJECT) -> None:
    # This will trigger the Task-level TypeError handler
    raise TypeError("Something went wrong in the task")

app.include_router(router)

async def main() -> None:
    async with app:
        job = await process_report.push()
        await job.wait()

if __name__ == "__main__":
    asyncio.run(main())
```

In this example:

- If `process_report` raises a `TypeError`, the **Task-level** handler will run.
- If it raises a `ValueError`, no custom handler will run (unless one is defined globally).
- If another task in the same router raises a `TypeError` (and doesn't have its own task-level handler), the **Router-level** handler will run.
- If a task outside this router raises a `TypeError`, the **Global-level** handler will run.
