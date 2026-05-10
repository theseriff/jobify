# Scheduling Jobs

Jobify supports two scheduling models:

- **Declarative**: define recurring schedules in `@app.task(cron=...)`
- **Dynamic**: schedule jobs at runtime via `.push()`, `.schedule().delay()`, `.schedule().at()`, `.schedule().cron()`

!!! info "Precision and System Time"
    Jobify uses event-loop timers instead of polling. It is efficient and precise, but sensitive to significant system time shifts.
    See [System Time and Scheduling Trade-offs](advanced_usage/system_time.md){ data-preview }.

<div class="grid cards" markdown>

-   :material-clock-outline:{ .lg .middle } __Declarative Cron__

    ---

    Stable recurring jobs defined in code and restored on startup.

-   :material-lightning-bolt-outline:{ .lg .middle } __Dynamic Scheduling__

    ---

    Runtime scheduling for immediate, delayed, absolute-time, or dynamic cron jobs.

-   :material-swap-horizontal-circle-outline:{ .lg .middle } __Idempotent Updates__

    ---

    `replace` and `force` control rescheduling behavior and outer middleware execution.

-   :material-history:{ .lg .middle } __Misfire Policies__

    ---

    Handle missed schedules with `ALL`, `SKIP`, `ONCE`, or `GRACE` windows.

</div>

## Scheduling API Quick Map

| Method | Use case | Key options |
| --- | --- | --- |
| `await task.push(*args, **kwargs)` | run as soon as possible | none |
| `await task.schedule(*args, **kwargs).delay(seconds, ...)` | run after delay | `job_id`, `now`, `replace` |
| `await task.schedule(*args, **kwargs).at(at, ...)` | run at exact `datetime` | `job_id`, `replace`, `force` |
| `await task.schedule(*args, **kwargs).cron(cron, ...)` | dynamic recurring schedule | `job_id` (required), `replace`, `force` |

## Cron Expressions

Jobify uses the [`crontab`](https://pypi.org/project/crontab/) parser.

### Syntax

```text
<seconds> <minutes> <hours> <day_of_month> <month> <day_of_week> <year>
```

### Expression formats

- **5 fields**: `MINUTES HOURS DAY_OF_MONTH MONTH DAY_OF_WEEK`
  - Example: `* * * * *` (every minute)
- **6 fields**: `MINUTES HOURS DAY_OF_MONTH MONTH DAY_OF_WEEK YEAR`
  - Example: `0 9 * * 1 2026`
- **7 fields**: `SECONDS MINUTES HOURS DAY_OF_MONTH MONTH DAY_OF_WEEK YEAR`
  - Example: `*/15 * * * * * *` (every 15 seconds)

!!! warning "Second-level precision"
    Use the **7-field** format for seconds.
    In this parser, 6 fields are interpreted with a **year** field, not seconds.

### Fields

| Field | Allowed values | Special characters |
| --- | --- | --- |
| `seconds` | `0-59` | `*`, `/`, `,`, `-` |
| `minutes` | `0-59` | `*`, `/`, `,`, `-` |
| `hours` | `0-23` | `*`, `/`, `,`, `-` |
| `day_of_month` | `1-31` | `*`, `/`, `,`, `-`, `?`, `L` |
| `month` | `1-12` or `JAN-DEC` | `*`, `/`, `,`, `-` |
| `day_of_week` | `0-6` or `SUN-SAT` | `*`, `/`, `,`, `-`, `?`, `L` |
| `year` | `1970-2099` | `*`, `/`, `,`, `-` |

### Predefined aliases

| Alias | Equivalent | Description |
| --- | --- | --- |
| `@yearly` | `0 0 1 1 *` | once a year |
| `@monthly` | `0 0 1 * *` | once a month |
| `@weekly` | `0 0 * * 0` | once a week |
| `@daily` | `0 0 * * *` | once a day |
| `@hourly` | `0 * * * *` | once an hour |

## The Cron Object

Use `Cron(...)` when you need scheduling policy controls beyond plain expression strings.

```python
from datetime import datetime

from jobify import Cron, MisfirePolicy

cron = Cron(
    "0 18 * * 1-5",
    max_runs=100,
    max_failures=5,
    misfire_policy=MisfirePolicy.ALL,
    start_date=datetime(2027, 1, 1),
    args=("sales",),
    kwargs={"file_format": "csv"},
)
```

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `expression` | `str` | required | cron expression |
| `max_runs` | `int` | `INFINITY (-1)` | max successful+failed run attempts before removal |
| `max_failures` | `int` | `10` | consecutive failure threshold before permanent stop |
| `misfire_policy` | `MisfirePolicy | GracePolicy` | `MisfirePolicy.ONCE` | missed-schedule behavior |
| `start_date` | `datetime | None` | `None` | anchor for first execution |
| `args` | `Collection[Any]` | `()` | positional arguments for scheduled executions |
| `kwargs` | `Mapping[str, Any]` | `{}` | keyword arguments for scheduled executions |

Misfire policies:

- `MisfirePolicy.ALL`: run all missed executions immediately.
- `MisfirePolicy.SKIP`: skip missed executions.
- `MisfirePolicy.ONCE`: run only once if there were misses.
- `MisfirePolicy.GRACE(timedelta)`: run only if miss is within grace window.

## Dynamic Scheduling

Start by creating a builder:

```python
builder = my_task.schedule(*args, **kwargs)
```

Then choose one of the methods below.

### cron

Create/update a recurring dynamic cron job.

```python
await my_task.schedule(*args, **kwargs).cron(
    cron="*/5 * * * *",
    job_id="cleanup_dynamic",  # required
    replace=False,
    force=False,
)
```

- `job_id` is required.
- if `replace=False` and `job_id` already exists, `DuplicateJobError` is raised.
- if `replace=True`, existing schedule is updated.
- if `force=False` and schedule is unchanged, Jobify returns existing job without re-running outer middleware.

!!! warning "Outer middleware execution"
    Outer middleware runs when a job is created/changed.
    Use `force=True` to run outer middleware even when scheduling config is unchanged.

### push (Immediate Execution)

Fastest way to enqueue a task for execution as soon as possible.

```python
job = await my_task.push(*args, **kwargs)
await job.wait()
```

!!! note "Persistence"
    `push()` jobs are also persisted when task is `durable=True`.
    If task is `durable=False`, they are not restored after restart.

### delay

Schedule execution after a delay in seconds.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

job = await my_task.schedule(*args, **kwargs).delay(
    seconds=60,
    job_id="email_60s",
    now=datetime.now(tz=ZoneInfo("UTC")),  # optional reference point
    replace=False,
)
```

Parameters:

- `seconds: float`
- `job_id: str | None = None`
- `now: datetime | None = None`
- `replace: bool = False`

!!! note
    `delay()` does not expose `force`; use `.at(..., force=True)` if you need force semantics for absolute-time rescheduling.

### at

Schedule execution at an exact `datetime`.

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

run_at = datetime.now(tz=ZoneInfo("UTC")) + timedelta(minutes=10)
job = await my_task.schedule(*args, **kwargs).at(
    at=run_at,
    job_id="report_123",
    replace=False,
    force=False,
)
```

Parameters:

- `at: datetime`
- `job_id: str | None = None`
- `replace: bool = False`
- `force: bool = False`

## Replacement and Duplicate IDs

By default, reusing an existing `job_id` raises `DuplicateJobError`.
You can set `replace=True` in `cron`, `delay`, or `at` to update existing schedule instead.

For cron jobs, replacement keeps offset/progress semantics unless relevant cron anchoring fields (for example `start_date`) change.
