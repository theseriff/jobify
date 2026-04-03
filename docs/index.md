# Jobify

**Jobify** is a powerful asynchronous job scheduling and management framework for Python.
It allows you to define and schedule background jobs with an intuitive decorator-based API,
similar to modern web frameworks like FastAPI.

## Key Features

- [**Precision**](#why-jobify){ data-preview }: No polling! Uses native `asyncio` timers for sub-millisecond accuracy and zero idle CPU usage.
- [**Scheduling**](schedule.md){ data-preview }: Run jobs immediately, with a delay, at a specified time, or using Cron expressions (second-level precision supported).
- [**Storage**](app_settings.md#storage){ data-preview }: Built-in SQLite ensures scheduled jobs persist through application restarts.
- [**Routing**](router.md){ data-preview }: Organize tasks with `JobRouter`, similar to FastAPI or Aiogram.
- [**Inject Context**](context.md){ data-preview }: Inject application state or custom dependencies directly into your tasks.
- [**Middlewares**](app_settings.md#middleware){ data-preview }: Powerful interceptors for both job execution and the scheduling process.
- [**Exception Handlers**](advanced_usage/exception_handlers.md){ data-preview }: Hierarchical error management at the task, router, or global level.
- [**Lifespan Support**](app_settings.md#lifespan){ data-preview }: Manage startup and shutdown events, just like in FastAPI.
- [**Job Control**](job.md){ data-preview }: Full control over jobs — wait for completion, cancel tasks, or check results with ease.
- [**Concurrency**](task_settings.md#run_mode){ data-preview }: Supports `asyncio`, `ThreadPoolExecutor`, and `ProcessPoolExecutor` for efficient task handling.
- [**Many different adapters to the database**](https://github.com/Jobify-Community/jobify-db).
- **Distributed task queue**: Soon.
- **Many different serializers**: Soon.

## Comparison

You might have seen other libraries like `APScheduler`, `Celery`, or `Taskiq`.
Below is a comparison of features to help you decide if Jobify fits your needs.

| Feature name                                                                   |        Jobify        |      Taskiq       | APScheduler (v3) |      Celery       |
| :----------------------------------------------------------------------------- | :------------------: | :---------------: | :--------------: | :---------------: |
| **Event-driven Scheduling**                                                    | ✅ (Low-level timer) | ❌ (Polling/Loop) |  ❌ (Interval)   | ❌ (Polling/Loop) |
| **Async Native (asyncio)**                                                     |          ✅          |        ✅         | ❌ (Sync mostly) |        ❌         |
| [**Context Injection**](context.md){ data-preview }                            |          ✅          |        ✅         |        ❌        |        ❌         |
| [**FastAPI-style Routing**](router.md){ data-preview }                         |          ✅          |        ❌         |        ❌        |        ❌         |
| [**Middleware Support**](app_settings.md#middleware){ data-preview }           |          ✅          |        ✅         | ❌ (Events only) |   ❌ (Signals)    |
| [**Lifespan Support**](app_settings.md#lifespan){ data-preview }               |          ✅          |        ✅         |        ❌        |        ❌         |
| [**Exception Handlers**](advanced_usage/exception_handlers.md){ data-preview } |  ✅ (Hierarchical)   |        ❌         |        ❌        |        ❌         |
| [**Job Cancellation**](job.md#await-jobcancel){ data-preview }                 |          ✅          |        ❌         |        ✅        |        ✅         |
| [**Cron Scheduling**](schedule.md#cron-expressions){ data-preview }            |  ✅ (Seconds level)  |   ✅ (Minutes)    |        ✅        |        ✅         |
| [**Misfire Policy**](schedule.md#the-cron-object){ data-preview }              |          ✅          |        ❌         |        ✅        |        ❌         |
| [**Run Modes (Thread/Process)**](task_settings.md#run_mode){ data-preview }    |          ✅          |        ✅         |        ✅        |        ✅         |
| **Rich Typing Support**                                                        |          ✅          |        ✅         |        ❌        |        ❌         |
| **Zero-config Persistence**                                                    | ✅ (SQLite default)  | ❌ (Needs Broker) |        ✅        | ❌ (Needs Broker) |
| **Broker-backend execution**                                                   |      ❌ (soon)       |        ✅         |        ❌        |        ✅         |

### Why Jobify?

Unlike many other frameworks that use a while True loop to continuously check the current time against scheduled tasks (polling),
Jobify uses the low-level asyncio.loop.call_at API.

1. **Efficiency**: The scheduler does not consume CPU cycles if there are no tasks to process.
2. **Precision**: Tasks are triggered precisely by the internal timer of the event loop, ensuring sub-millisecond accuracy and avoiding the "jitter" that can be associated with sleep intervals.
3. **Native**: It works in harmony with OS-level event notification systems (epoll/kqueue).

!!! note "The Precision vs. Polling Trade-off"
    Jobify consciously avoids polling in order to achieve maximum efficiency and sub-millisecond precision. This architectural decision means that the scheduler is sensitive to significant changes in the operating system's clock. For more information on this trade-off and why it is important, please see [System Time and Scheduling](advanced_usage/system_time.md){ data-preview }.

## Quick Start

### Installation

```bash
pip install jobify
```

### Basic Usage

Here is a simple example showing how to define a task and schedule it.

```python linenums="1" hl_lines="27 31 34 37-40"
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jobify import Jobify

UTC = ZoneInfo("UTC")
# 1. Initialize Jobify
app = Jobify(tz=UTC)


@app.task(cron="* * * * * * *")  # Runs every second
async def my_cron() -> None:
    print("Hello! cron running every second")


@app.task
def my_job(name: str) -> None:
    now = datetime.now(tz=UTC)
    print(f"Hello, {name}! job running at: {now!r}")


async def main() -> None:
    # 4. Run the Jobify application context
    async with app:
        # Run immediately in the background.
        job = await my_job.push("Alex")

        # Schedule a one-time job at a specific time.
        run_next_day = datetime.now(tz=UTC) + timedelta(days=1)
        job_at = await my_job.schedule("Connor").at(run_next_day)

        # Schedule a one-time job after a delay.
        job_delay = await my_job.schedule("Sara").delay(20)

        # Start a dynamic cron job.
        job_cron = await my_cron.schedule().cron(
            "* * * * *",
            job_id="dynamic_cron_id",
        )

        await job_at.wait()
        await job_delay.wait()
        await job_cron.wait()
        # You can also use the `await app.wait_all()` method to wait for
        # all currently running jobs to complete.
        # Note: If there are infinitely running cron jobs, like `my_cron`,
        # `app.wait_all()` will block indefinitely until a timeout is set.
        # await app.wait_all()


if __name__ == "__main__":
    asyncio.run(main())

```
