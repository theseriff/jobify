# Task Configuration

You can also configure individual tasks by passing arguments to the `@app.task` decorator.

```python
from jobber import Cron, Jobber, RunMode

app = Jobber()


@app.task(
    func_name="my_daily_report",
    # When the app restarts, the max_runs is set to 0 and the app again runs 30 times.
    cron=Cron("* * * * *", max_runs=30, max_failures=4),


    retry=3,
    timeout=300,  # in seconds
    durable=True,
    run_mode=RunMode.PROCESS,
    metadata={"key1": "somekey_for_metadata"},
)
def my_daily_report() -> None:
    pass
```

## `cron`

- **Type**: `str | Cron`
- **Default**: `None`

A cron expression is used to schedule a task to be executed repeatedly.
You can pass either a simple cron expression or an instance of the `Cron` class to have more control over the scheduling of the job.

```python
from jobber import Cron

@app.task(
    cron=Cron("0 18 * * 1-5", max_runs=100, max_failures=5)
)
def my_daily_report():
    ...
```

The `Cron` class has the following properties:

- **`expression`** (`str`): The cron expression as a string.
- **`max_runs`** (`int`, default: `INFINITY (-1)`): The maximum number of times a job can run. After a job has run this many times, it will no longer be scheduled for execution.
- **`max_failures`** (`int`, default: `10`): The maximum number of consecutive failed attempts allowed before a job is permanently stopped and no longer scheduled. This value must be greater than or equal to 1.

## `retry`

- **Type**: `int`
- **Default**: `None` (no retries)

The number of times the task should be automatically retried if it fails.

## `timeout`

- **Type**: `float`
- **Default**: `None` (no timeout)

The maximum time allowed for the task to complete before it is stopped and considered a timeout, is in seconds.

## `durable`

- **Type**: `bool`
- **Default**: `True`

If `True`, the job will be stored in a persistent location and will survive a restart of the application. `Durable` jobs are restored when the Jobber app starts up.

## `run_mode`

- **Type**: `'RunMode.MAIN' | 'RunMode.THREAD' | 'RunMode.PROCESS'`
- **Default**: `'RunMode.MAIN'` for `async` functions, `'RunMode.THREAD'` for `sync` functions.

Specifies the mode of execution for the task.

- `'RunMode.MAIN'`: For `#!python async def`. Runs on the main asyncio event loop. This is the default mode for async functions.
- `'RunMode.THREAD'`: For `#!python def` functions. This runs in the `ThreadPoolExecutor`, which is the default for synchronous functions.
- `'RunMode.PROCESS'`: This mode is used for `#!python def` definitions. It runs in the `ProcessPoolExecutor`.

## `metadata`

- **Type**: `Mapping[str, Any] | None`
- **Default**: `None`

A dictionary of key-value pairs that can be used to attach custom metadata to a job.
This data is not used directly by Jobber, but it can be useful for other parts of your application, such as middleware or debugging tools.
