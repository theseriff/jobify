# Jobber

**Jobber** is a powerful asynchronous job scheduling and management framework for Python.
It allows you to define and schedule background jobs with an intuitive decorator-based API,
similar to modern web frameworks like FastAPI.

## Key Features

- **Async First**: Built on top of `asyncio`.
- **Flexible Scheduling**: Run jobs immediately, after a delay, at a specific time, or via Cron expressions.
- **Persistence**: Built-in SQLite storage ensures scheduled jobs survive application restarts.
- **Modular**: Organize tasks using `JobRouter`s (similar to FastAPI routers).
- **Resilient**: Middleware support for automatic retries, timeouts, and error handling.
- **Concurrency**: Support for `asyncio`, `ThreadPoolExecutor`, and `ProcessPoolExecutor`.

## Comparison

You might have seen other libraries like `APScheduler`, `Celery`, or `Taskiq`.
Below is a comparison of features to help you decide if Jobber fits your needs.

| Feature name                   |       Jobber        |      Taskiq       | APScheduler (v3) |      Celery       |
| :----------------------------- | :-----------------: | :---------------: | :--------------: | :---------------: |
| **Async Native (asyncio)**     |         ✅          |        ✅         | ❌ (Sync mostly) |        ❌         |
| **Zero-config Persistence**    | ✅ (SQLite default) | ❌ (Needs Broker) |        ✅        | ❌ (Needs Broker) |
| **Dependency Injection**       |         ✅          |        ✅         |        ❌        |        ❌         |
| **FastAPI-style Routing**      |         ✅          |        ❌         |        ❌        |        ❌         |
| **Middleware Support**         |         ✅          |        ✅         | ❌ (Events only) |   ❌ (Signals)    |
| **Job Cancellation**           |         ✅          |        ❌         |        ✅        |        ✅         |
| **Cron Scheduling**            |         ✅          |        ✅         |        ✅        |        ✅         |
| **Run Modes (Thread/Process)** |         ✅          |        ✅         |        ✅        |        ✅         |
| **Rich Typing Support**        |         ✅          |        ✅         |        ❌        |        ❌         |
| **Broker-backend execution**   |      ❌ (soon)      |        ✅         |        ❌        |        ✅         |

## Quick Start

### Installation

```bash
pip install jobber
```

### Basic Usage

Here is a simple example showing how to define a task and schedule it.

```python linenums="1" hl_lines="27 29 31"
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jobber import Jobber

UTC = ZoneInfo("UTC")
# 1. Initialize Jobber
app = Jobber(tz=UTC)


@app.task(cron="* * * * * * *")  # Runs every seconds
async def my_cron() -> None:
    print("Hello! cron running every seconds")


@app.task
def my_job(name: str) -> None:
    now = datetime.now(tz=UTC)
    print(f"Hello, {name}! job running at: {now!r}")


async def main() -> None:
    # 4. Run the Jobber application context
    async with app:
        run_next_day = datetime.now(tz=UTC) + timedelta(days=1)
        job_at = await my_job.schedule("Connor").at(run_next_day)

        job_delay = await my_job.schedule("Sara").delay(20)

        job_cron = await my_cron.schedule("Mike").cron("* * * * *")

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
