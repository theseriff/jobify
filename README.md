<div align="center">

<h1>Jobify<br>Robust task scheduler for Python.</h1>

[![Supported Python versions](https://img.shields.io/pypi/pyversions/jobify.svg)](https://pypi.org/project/jobify)
[![Tests](https://github.com/theseriff/jobify/actions/workflows/pr_tests.yml/badge.svg)](https://github.com/theseriff/jobify/actions/workflows/pr_tests.yml)
[![Coverage](https://coverage-badge.samuelcolvin.workers.dev/theseriff/jobify.svg)](https://coverage-badge.samuelcolvin.workers.dev/redirect/theseriff/jobify)
[![CodeQL](https://github.com/theseriff/jobify/actions/workflows/pr_codeql.yml/badge.svg)](https://github.com/theseriff/jobify/actions/workflows/pr_codeql.yml)
[![Dependency Review](https://github.com/theseriff/jobify/actions/workflows/pr_dependency_review.yml/badge.svg)](https://github.com/theseriff/jobify/actions/workflows/pr_dependency_review.yml)
[![PyPI version](https://badge.fury.io/py/jobify.svg)](https://pypi.python.org/pypi/jobify)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

**Documentation**: [https://theseriff.github.io/jobify/](https://theseriff.github.io/jobify/)

**Jobify** is a powerful framework for scheduling and managing background jobs in Python.
It allows you to easily define and schedule jobs using an intuitive decorator-based API, similar to that of modern web frameworks such as FastAPI.

Unlike many other frameworks that use polling (continuous loops) to schedule tasks,
Jobify uses the native timer mechanisms of asyncio for efficient and precise task scheduling.

## Key Features

- **Async/Await**: Built from the ground up with `asyncio` in mind.
- **Scheduling**: Run jobs immediately, with a delay, at a specified time, or using Cron expressions (second-level precision supported).
- **Storage**: Built-in SQLite ensures scheduled jobs persist through application restarts.
- **Routing**: Organize tasks with `JobRouter`, similar to FastAPI or Aiogram.
- **Error Handling**: Comprehensive middleware for automatic retries, timeouts, and custom error handling.
- **Concurrency**: Supports `asyncio`, `ThreadPoolExecutor`, and `ProcessPoolExecutor` for efficient task handling.
- **Dependency Injection**: Powerful system for injecting job contexts.

## Installation

Install Jobify from PyPI:

```bash
pip install jobify
```

## Quick Start

Here is an example of how to define and schedule a task:

```python
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jobify import Jobify

UTC = ZoneInfo("UTC")

# 1. Initialize Jobify
app = Jobify(tz=UTC)


@app.task(cron="* * * * * * *")  # Runs every second
async def my_cron(name: str) -> None:
    print(f"Hello, {name}! cron running every second")


@app.task
def my_job(name: str) -> None:
    now = datetime.now(tz=UTC)
    print(f"Hello, {name}! job running at: {now!r}")


async def main() -> None:
    # 2. Run the Jobify application context
    async with app:
        # Schedule a one-time job at a specific time
        run_next_day = datetime.now(tz=UTC) + timedelta(days=1)
        job_at = await my_job.schedule("Connor").at(run_next_day)

        # Schedule a one-time job after a delay
        job_delay = await my_job.schedule("Sara").delay(seconds=20)

        # Start a dynamic cron job
        job_cron = await my_cron.schedule("Mike").cron(
            "* * * * *",
            job_id="dynamic_cron_id",
        )

        # Wait for specific jobs to complete
        await job_delay.wait()

        # You can also use `await app.wait_all()` to wait for all currently
        # running jobs. Note that infinite cron jobs will block this indefinitely.
        # await app.wait_all()


if __name__ == "__main__":
    asyncio.run(main())
```

## License

This project is licensed under the terms of the [MIT license](https://github.com/theseriff/jobify/blob/main/LICENSE).
