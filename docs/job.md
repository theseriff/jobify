# The Job Object

Every scheduling call returns a `Job` handle:

- `await task.push(...)`
- `await task.schedule(...).delay(...)`
- `await task.schedule(...).at(...)`
- `await task.schedule(...).cron(...)`

Use this handle to observe state, wait for completion, read result, or cancel.

<div class="grid cards" markdown>

-   :material-timer-sand:{ .lg .middle } __Track__

    ---

    Inspect `job.id`, `job.status`, `job.exec_at`, `job.cron_expression`.

-   :material-progress-clock:{ .lg .middle } __Await__

    ---

    `await job.wait()` or `result = await job`.

-   :material-cancel:{ .lg .middle } __Control__

    ---

    `await job.cancel()` for scheduled/queued jobs.

-   :material-list-status:{ .lg .middle } __Status Checks__

    ---

    Helpers like `job.is_done()` and `job.is_cron()` for quick logic branching.

</div>

## Quick Example

```python
import asyncio

from jobify import Jobify, JobStatus

app = Jobify()


@app.task
def add(x: int, y: int) -> int:
    return x + y


async def main() -> None:
    async with app:
        job = await add.schedule(1, 2).delay(1)
        print(job.id, job.status)

        await job.wait()
        if job.status is JobStatus.SUCCESS:
            print(job.result())  # 3


if __name__ == "__main__":
    asyncio.run(main())
```

## Job Attributes

### `job.id`

- **Type**: `str`

Unique identifier for the scheduled job instance.

### `job.status`

- **Type**: `JobStatus`

Current state value. Possible statuses:

- `PENDING`: internal initial state before scheduler registration.
- `SCHEDULED`: registered and waiting for execution.
- `RUNNING`: currently executing.
- `CANCELLED`: cancelled by user or lifecycle cleanup.
- `SUCCESS`: completed with result.
- `FAILED`: completed with failure exception.
- `TIMEOUT`: stopped by timeout policy.
- `PERMANENTLY_FAILED`: cron job stopped by max-failures policy.

### `job.exec_at`

- **Type**: `datetime`

Timezone-aware execution timestamp.

### `job.cron_expression`

- **Type**: `str | None`

- Cron jobs: returns expression string.
- One-shot jobs (`push/at/delay`): `None`.

### `job.exception`

- **Type**: `Exception | None`

Holds execution exception for terminal error states (for example `FAILED`, `TIMEOUT`).

## Interacting with a Job

### Waiting for completion

#### `await job.wait()`

Waits until the job reaches terminal state.
It does **not** raise task exceptions itself.

```python
await job.wait()
print(job.status)
```

#### `job.result()`

Reads result from a completed job.

Behavior:

- returns value when status is `SUCCESS`
- raises `JobFailedError` when status is `FAILED`
- raises `JobNotCompletedError` for non-ready or non-result states

```python
await job.wait()
value = job.result()
```

### Awaitable shorthand

#### `await job`

Equivalent pattern:

1. wait for completion
2. return `job.result()`

```python
result = await job
```

Useful for batching:

```python
jobs = [await add.schedule(i, i).delay(0) for i in range(3)]
results = await asyncio.gather(*jobs)
```

### Cancelling a Job

#### `await job.cancel()`

Cancels and unschedules the job handle, including persistence cleanup for durable schedules.

```python
job = await add.schedule(10, 20).delay(300)
await job.cancel()
```

Use this for jobs that are scheduled but no longer needed.

### Status helpers

#### `job.is_done()`

Returns `True` when job reached terminal state, else `False`.

```python
if job.is_done():
    print(job.status)
```

#### `job.is_cron()`

Returns `True` if this handle represents cron schedule execution context.

```python
if job.is_cron():
    print(job.cron_expression)
```

## Recommended Patterns

=== "Concise await style"

    ```python
    try:
        data = await job
    except Exception as exc:
        print("job failed:", exc)
    ```

=== "Concurrent waits"

    ```python
    jobs = [
        await add.schedule(1, 1).delay(0),
        await add.schedule(2, 2).delay(0),
    ]
    await asyncio.gather(*(job.wait() for job in jobs))
    ```
