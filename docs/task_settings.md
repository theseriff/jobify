# Task Configuration

Use `@app.task(...)` (or `@router.task(...)`) to configure per-task behavior: schedule policy, retries, timeout, durability, execution mode, metadata, and handlers.

<div class="grid cards" markdown>

- :material-calendar-sync-outline:{ .lg .middle } **Scheduling**

    ***

    `cron`, `durable`, and task `name` for stable schedule identity.

- :material-restart-alert:{ .lg .middle } **Reliability**

    ***

    `retry`, `timeout`, and task-level `exception_handlers`.

- :material-cog-transfer-outline:{ .lg .middle } **Execution Control**

    ***

    `run_mode` and `metadata` for middleware-driven policies.

- :material-shield-alert-outline:{ .lg .middle } **Error Handling**

    ***

    Task-specific `exception_handlers` for localized recovery logic.

</div>

## Example

```python
from jobify import Cron, Jobify, MisfirePolicy, RunMode

app = Jobify()


@app.task(
    name="reports:daily",
    cron=Cron(
        "0 8 * * 1-5",
        max_runs=100,
        max_failures=5,
        misfire_policy=MisfirePolicy.SKIP,
    ),
    retry=3,
    timeout=300,
    durable=True,
    run_mode=RunMode.PROCESS,
    metadata={"priority": 100, "team": "finance"},
    exception_handlers={TimeoutError: lambda exc, ctx: "timed_out"},
)
def daily_report() -> None:
    ...
```

## name

- **Type**: `str`
- **Default**: auto-generated from function (`module:qualname`)

Defines the unique task/route name.
Set it explicitly when you need stable naming across refactors, imports, or deployments.

```python
@app.task(name="billing:close_invoices")
def close_invoices() -> None:
    ...
```

## cron

- **Type**: `str | Cron`
- **Default**: not set

Registers a declarative recurring schedule on app startup.
Use `Cron(...)` when you need advanced options (`max_runs`, `misfire_policy`, `start_date`, args/kwargs).

```python
from datetime import datetime

from jobify import Cron, MisfirePolicy


@app.task(
    cron=Cron(
        "0 18 * * 1-5",
        max_runs=100,
        max_failures=5,
        misfire_policy=MisfirePolicy.ALL,
        start_date=datetime(2027, 1, 1),
        args=("financial",),
        kwargs={"recipient": "admin@example.com"},
    )
)
def daily_report(report_type: str, recipient: str) -> None:
    ...
```

See [The Cron Object](schedule.md#the-cron-object){ data-preview } for full details.

## retry

- **Type**: `int`
- **Default**: not set (no retries)

Number of retry attempts after failure.

```python
@app.task(retry=3)
def fragile_io() -> None:
    ...
```

## timeout

- **Type**: `float`
- **Default**: not set (no timeout)

Execution timeout in seconds. If exceeded, task is marked as timeout/failure path.

```python
@app.task(timeout=30.0)
async def slow_task() -> None:
    ...
```

## durable

- **Type**: `bool`
- **Default**: `True`

Controls whether scheduled jobs are persisted and restored after restart.

!!! tip "High-frequency cron optimization"
    For very high-frequency cron jobs (for example every second), consider `durable=False`
    to reduce storage churn and write load.

```python
@app.task(cron="* * * * * * *", durable=False)
async def heartbeat() -> None:
    ...
```

## run_mode

- **Type**: `RunMode.MAIN | RunMode.THREAD | RunMode.PROCESS`
- **Default**:
    - async functions: `RunMode.MAIN`
    - sync functions: `RunMode.THREAD`

Execution model for the task function.

- `RunMode.MAIN`: run on event loop (`async def`).
- `RunMode.THREAD`: run sync function in `ThreadPoolExecutor`.
- `RunMode.PROCESS`: run sync function in `ProcessPoolExecutor`.

```python
from jobify import RunMode


@app.task(run_mode=RunMode.MAIN)
async def async_job() -> None:
    ...


@app.task(run_mode=RunMode.THREAD)
def sync_io_job() -> None:
    ...


@app.task(run_mode=RunMode.PROCESS)
def cpu_heavy_job() -> None:
    ...
```

!!! note "Async + THREAD/PROCESS"
    If function is `async def`, Jobify keeps execution in `MAIN` loop.
    Setting `THREAD`/`PROCESS` for async function is ignored with runtime warning semantics.

## exception_handlers

- **Type**: `MappingExceptionHandlers | None`
- **Default**: not set

Task-local exception map. Takes precedence over router-level and global handlers.

```python
from jobify import JobContext


def on_value_error(exc: Exception, context: JobContext) -> str:
    return "fallback"


@app.task(exception_handlers={ValueError: on_value_error})
def task_with_recovery() -> None:
    ...
```

[Read detailed guide](advanced_usage/exception_handlers.md){ data-preview }

## metadata

- **Type**: `Mapping[str, Any] | None`
- **Default**: not set

Custom task attributes used by middleware/policies.
Common patterns: priority, tenant routing, feature flags, skip/debug markers.

```python
@app.task(metadata={"priority": 100, "tenant": "acme"})
async def critical_pipeline() -> None:
    ...
```

With `QueueMiddleware`, larger `metadata.priority` values run earlier in `PriorityQueue` mode.
