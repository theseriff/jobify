# The Job Object

When you schedule a task using the `.at()` or `.delay()` methods, or the `.cron()` function, you receive a Job object.
This object serves as a handle for that particular scheduled task, allowing you to monitor its progress,
wait for it to complete, or cancel it if necessary.

You do not create `Job` objects directly.

```python
import asyncio

from jobber import Jobber

app = Jobber()


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

You can inspect a `Job` object to get information about its status.

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

### `await job.wait()`

The job waits for completion. If the job is already finished, it immediately returns.
This is useful to ensure that a specific task has been completed before moving on to the next step.

```python
job = await my_task.schedule(...).delay(5)
# ... do other things ...
print("Waiting for the job to finish...")
await job.wait()
print("Job finished!")
```

### `job.result()`

This method retrieves the result of the task. It should only be used after the task has been completed successfully.

- If the job's status is `SUCCESS`, it returns the result.
- If the job's status is `FAILED` or `TIMEOUT`, it raises a `JobFailedError` which wraps the original exception.
- If the job is not completed, it will raise a `JobNotCompletedError`.

```python
await job.wait()
if job.status == JobStatus.SUCCESS:
    result = job.result()
    print(f"The task returned: {result}")
```

### `await job.cancel()`

Cancels a scheduled job before it starts running. If the job is already running or has completed, this action has no effect.
This also removes the job from any persistent storage.

```python
job_to_cancel = await my_task.schedule(...).delay(300)
# ... later ...
await job_to_cancel.cancel()
print(f"Job {job_to_cancel.id} has been cancelled.")
```

### `job.is_done()`

Returns `True` if the job has completed execution (regardless of whether it was successful, failed, or cancelled), and `False` otherwise.
This method is non-blocking and can be used to quickly check the status of a job.

```python
if job.is_done():
    print(f"Job {job.id} is done with status {job.status}")
```
