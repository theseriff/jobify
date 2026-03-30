# The Job Object

When you schedule a task using the `.at()` or `.delay()` methods or the `.push()` function or the `.cron()` method, you will receive a Job object.
This object acts as a handle for the scheduled task, allowing you to track its progress, wait for it to finish, or cancel it if needed.

You do not create `Job` objects directly.

```python
import asyncio

from jobify import Jobify

app = Jobify()


@app.task
def my_task(x: int, y: int) -> int:
    return x + y


async def main() -> None:
    async with app:
        # Scheduling a task returns a Job instance
        job = await my_task.schedule(1, 2).delay(1)
        print(f"Job {job.id} was scheduled.")
        await job.wait()  # Wait for this specific job to complete
        print(f"Job {job.id} finished with status: {job.status}")
        print(f"Result: {job.result()}")


if __name__ == "__main__":
    asyncio.run(main())
```

## Job Details

You can inspect a `Job` object to get information about its current status.

### `job.id`

- **Type**: `str`

A unique identifier for this specific job instance.

### `job.status`

- **Type**: `JobStatus` (Enum)

The current status of the job can be one of the following:

- `SCHEDULED`: The job has been scheduled and is waiting to be run.
- `RUNNING`: The job is currently running.
- `CANCELLED`: The job was cancelled before it could be completed.
- `SUCCESS`: The job was completed successfully.
- `FAILED`: The job failed due to an unexpected error during execution.
- `TIMEOUT`: The job has been terminated because it has exceeded its execution time limit.
- `PERMANENTLY_FAILED`: A recurring (cron) job that has been stopped because it has exceeded its maximum number of failures.

### `job.exec_at`

- **Type**: `datetime`

The timezone-aware `datetime` object indicating when the job is scheduled to be executed.

### `job.cron_expression`

- **Type**: `str | None`

If the job is a recurring task, this attribute contains the cron expression string.
If it is a one-time job scheduled using `.at()` or `.delay()` methods, it is set to `None`.

## Interacting with a Job

The `Job` object provides several methods for controlling and interacting with scheduled tasks.

### Waiting for Completion

There are two ways to wait for a job to complete:

#### `await job.wait()`

This method waits for the job to complete its execution. If the job has already completed, it immediately returns.
The method does not raise any exceptions if the job fails.

```python
job = await my_task.schedule(...).delay(5)
# ... do other things ...
print("Waiting for the job to finish...")
await job.wait()
print("Job finished!")
```

After calling `wait()`, you can check the status of the job and retrieve the result.

```python
await job.wait()
if job.status == JobStatus.SUCCESS:
    result = job.result()
    print(f"The task returned: {result}")
```

#### `job.result()`

Retrieves the result of the task. This method should only be called when the job is complete.

- If the job's status is `SUCCESS`, it returns the result.
- If the job's status is `FAILED` or `TIMEOUT`, it raises a `JobFailedError` wrapping the original exception.
- If the job is not yet completed, it raises a `JobNotCompletedError`.

```python
await job.wait()
result = job.result()  # May raise if job failed
```

#### `await job` (Awaitable)

The `Job` object can be directly awaited. Using `await job` provides a convenient shorthand for combining `await job.wait()` and `job.result()`,
as it waits for completion and returns the result in a single operation.

```python
job = await my_task.schedule(1, 2).delay(5)
# ... do other things ...
result = await job  # Wait and get result in one step
print(f"Job finished with result: {result}")
```

This is particularly useful when using `asyncio.gather()`, which allows you to wait for multiple tasks to complete concurrently.

```python
job1 = await my_task.schedule(1).delay(1)
job2 = await my_task.schedule(2).delay(2)
results: list = await asyncio.gather(job1, job2)  # Wait for both jobs
```

> **Note**: If the job function raises an exception, `await job` will propagate that exception.
> Use a `try`/`except` block to handle potential errors:
>
> ```python
> try:
>     result = await job
> except Exception as exc:
>     print(f"Job failed with: {exc}")
> ```
>
> **Which should you use?**

- If you want to manually handle success/failure based on the status, use `await job.wait() + job.result()`.
- If you prefer a more concise way to wait for and get the result, while being prepared to handle exceptions, use `await job`.

### Cancelling a Job

#### `await job.cancel()`

Cancels a scheduled job before it starts running. If the job is already running or has completed, this action has no effect.
This also removes the job from any persistent storage.

```python
job_to_cancel = await my_task.schedule(...).delay(300)
# ... later ...
await job_to_cancel.cancel()
print(f"Job {job_to_cancel.id} has been cancelled.")
```

### Checking Job Status

#### `job.is_done()`

Returns `True` if the job has completed execution (regardless of whether it was successful, failed, or cancelled), and `False` otherwise.
This method is non-blocking and can be used to quickly check the status of a job.

```python
if job.is_done():
    print(f"Job {job.id} is done with status {job.status}")
```
