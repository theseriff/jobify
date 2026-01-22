# Task Configuration

You can also configure individual tasks by passing arguments to the `@app.task` decorator.

```python
from jobify import Cron, Jobify, MisfirePolicy, RunMode

app = Jobify()


@app.task(
    name="my_daily_report",
    cron=Cron(
        "* * * * *",
        max_runs=30,
        max_failures=4,
        misfire_policy=MisfirePolicy.SKIP,
    ),
    retry=3,
    timeout=300,  # in seconds
    durable=True,
    run_mode=RunMode.PROCESS,
    metadata={"key1": "somekey_for_metadata"},
)
def my_daily_report() -> None:
    pass
```

## cron

- **Type**: `str | Cron`
- **Default**: `None`

A cron expression is used to schedule a task to be executed repeatedly.
You can pass either a simple cron expression or an instance of the `Cron` class to have more control over the scheduling of the job.

```python
from jobify import Cron, MisfirePolicy

@app.task(
    cron=Cron(
        "0 18 * * 1-5",
        max_runs=100,
        max_failures=5,
        misfire_policy=MisfirePolicy.ALL,
        start_date=datetime(2027, 1, 1), # The task will start on January 1, 2027.
    )
)
def my_daily_report() -> None:
    ...
```

For detailed information on the `Cron` object and its properties (such as `max_runs`, `misfire_policy`, etc.), please refer to the [The Cron Object](./schedule.md#the-cron-object){ data-preview } section in the scheduling documentation.

## retry

- **Type**: `int`
- **Default**: `None` (no retries)

The number of times the task should be automatically retried if it fails.

## timeout

- **Type**: `float`
- **Default**: `None` (no timeout)

The maximum time allowed for the task to complete before it is stopped and considered a timeout, is in seconds.

## durable

- **Type**: `bool`
- **Default**: `True`

If `True`, the job will be stored in a persistent location and will survive a restart of the application. `Durable` jobs are restored when the Jobify app starts up.

!!! note
    If you use a high-frequency cron job (for example, every second `* * * * * * *`), it is recommended to set "durable=False".
    This will help to prevent excessive load on the database when updating the task's status and improve overall performance.
    For such frequent tasks, it is usually not necessary to save the state between restarts.

## run_mode

- **Type**: `'RunMode.MAIN' | 'RunMode.THREAD' | 'RunMode.PROCESS'`
- **Default**: `'RunMode.MAIN'` for `async` functions, `'RunMode.THREAD'` for `sync` functions.

Specifies the mode of execution for the task.

- `'RunMode.MAIN'`: For `#!python async def`. Runs on the main asyncio event loop. This is the default mode for async functions.
- `'RunMode.THREAD'`: For `#!python def` functions. This runs in the `ThreadPoolExecutor`, which is the default for synchronous functions.
- `'RunMode.PROCESS'`: This mode is used for `#!python def` definitions. It runs in the `ProcessPoolExecutor`.

## metadata

- **Type**: `Mapping[str, Any] | None`
- **Default**: `None`

A dictionary of key-value pairs that can be used to attach custom metadata to a job.
This data is not used directly by Jobify, but it can be useful for other parts of your application, such as middleware or debugging tools.
