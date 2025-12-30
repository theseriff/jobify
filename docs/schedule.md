# Scheduling Jobs

You can schedule tasks in two main ways: using recurring cron expressions or dynamically at runtime.

## Cron Expressions

`Jobber` uses the [crontab](https://pypi.org/project/crontab/) library to parse and schedule jobs from cron expressions. This provides a flexible and powerful way to define recurring tasks.

### Syntax

A cron expression is a string of fields that describe a schedule. The `crontab` library supports standard 5-field cron expressions, but also expressions with 6 or 7 fields for second-level precision and year specification.

The general representation is:

```
<seconds> <minutes> <hours> <day_of_month> <month> <day_of_week> <year>
```

### Expression Formats

The `crontab` library supports multiple expression formats, which are interpreted as follows:

- **5 fields**: `MINUTES HOURS DAY_OF_MONTH MONTH DAY_OF_WEEK`
    - Example: `* * * * *` - runs every minute.

- **6 fields**: `MINUTES HOURS DAY_OF_MONTH MONTH DAY_OF_WEEK YEAR`
    - Example: `0 9 * * 1 2024` - runs at 9:00 AM every Monday in 2024.

- **7 fields**: `SECONDS MINUTES HOURS DAY_OF_MONTH MONTH DAY_OF_WEEK YEAR`
    - This is the format you must use for second-level precision.
    - Example: `*/15 * * * * * *` - runs every 15 seconds.

!!! warning
    To schedule a job with second-level precision (e.g., every 15 seconds),
    you must use a 7-field expression. A 6-field expression will be interpreted
    as including a YEAR field, not a SECONDS field.

### Fields

| Field          | Allowed Values  | Allowed Special Characters   |
| -------------- | --------------- | ---------------------------- |
| `seconds`      | 0-59            | `*`, `/`, `,`, `-`           |
| `minutes`      | 0-59            | `*`, `/`, `,`, `-`           |
| `hours`        | 0-23            | `*`, `/`, `,`, `-`           |
| `day_of_month` | 1-31            | `*`, `/`, `,`, `-`, `?`, `L` |
| `month`        | 1-12 or JAN-DEC | `*`, `/`, `,`, `-`           |
| `day_of_week`  | 0-6 or SUN-SAT  | `*`, `/`, `,`, `-`, `?`, `L` |
| `year`         | 1970-2099       | `*`, `/`, `,`, `-`           |

### Special Characters

- **`*` (Asterisk):** Selects all possible values for a field. For example, `*` in the `minutes` field means "every minute".
- **`,` (Comma)**: Used to specify a list of values. For example, "1, 5, 10" in the "minutes" field means "at minutes 1, 5 and 10".
- **`-` (Dash)**: Specifies a range of values. For example, `1-5` in the `day_of_week` field means "Monday to Friday."
- **`/` (Slash)**: Specifies a step value. For example, `/15` in the `seconds` field means "every 15 seconds."
- **`?` (Question Mark)**: Used in `day_of_month` or `day_of_week` to indicate "no specific value", which is useful when you want to specify one of these fields but not the other.
- **`L` (Last)**: has different meanings depending on the context. In **`day_of_month`** it refers to the last day of the month, while in **`day_of_week`** it means the last day of the week, which is Saturday.

### Predefined Expressions (Aliases)

You can also use one of the following predefined cron expressions:

| Expression | Equivalent  | Description                               |
| ---------- | ----------- | ----------------------------------------- |
| `@yearly`  | `0 0 1 1 *` | Run once a year, at midnight on Jan 1st.  |
| `@monthly` | `0 0 1 * *` | Run once a month, at midnight on the 1st. |
| `@weekly`  | `0 0 * * 0` | Run once a week, at midnight on Sunday.   |
| `@daily`   | `0 0 * * *` | Run once a day, at midnight.              |
| `@hourly`  | `0 * * * *` | Run once an hour, at the beginning.       |

For more detailed information, please refer to the official [crontab library documentation](https://pypi.org/project/crontab/).

## Dynamic Scheduling

In addition to cron jobs, you can also schedule tasks to run at a specific time or after a delay. This can be useful for one-time tasks or tasks that are triggered by application logic.

To dynamically schedule a task, you need to create a `ScheduleBuilder`. You can do this by calling the `.schedule()` method on the task function. The arguments that you pass to `.schedule()` will be used when the task runs.

### `delay`

To run a task after a specified delay, use the `delay()` method of the builder.

- **`delay(seconds: float)`**: Schedules the task to run after a specified number of seconds.

```python
import asyncio
from jobber import Jobber

app = Jobber()

@app.task
def send_email(to: str, subject: str) -> None:
    print(f"Sending email to {to} about {subject}")

async def main() -> None:
    async with app:
        # Schedule the email to be sent in 60 seconds
        job = await send_email.schedule(
            to="user@example.com",
            subject="Hello",
        ).delay(seconds=60)
        await job.wait()

asyncio.run(main())
```

### `at`

To run a task at a specific `datetime`, use the `.at()` method.

- **`at(at: datetime)`**: Schedules the task to run at the specified `datetime`.

```python
import asyncio
from datetime import datetime, timedelta
from jobber import Jobber

app = Jobber()

@app.task
def generate_report(report_id: int) -> None:
    print(f"Generating report {report_id}")

async def main() -> None:
    async with app:
        # Schedule the report to be generated 10 minutes from now
        run_time = datetime.now(app.configs.tz) + timedelta(minutes=10)
        job = await generate_report.schedule(report_id=123).at(at=run_time)
        # Keep the app running to allow the job to execute
        await job.wait()

asyncio.run(main())
```
