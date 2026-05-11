<div align="center">

<a href="https://theseriff.github.io/jobify/">
  <img src="https://raw.githubusercontent.com/theseriff/jobify/main/docs/images/logo.svg" alt="Jobify logo" width="140">
</a>

<h1>Jobify</h1>
<p><strong>Robust async task scheduler for Python.</strong></p>
<p>Event-driven timing, typed APIs, persistence, routing, and queue-based backpressure.</p>

[![Supported Python versions](https://img.shields.io/pypi/pyversions/jobify.svg)](https://pypi.org/project/jobify)
[![PyPI version](https://badge.fury.io/py/jobify.svg)](https://pypi.python.org/pypi/jobify)
[![Tests](https://github.com/theseriff/jobify/actions/workflows/pr_tests.yml/badge.svg)](https://github.com/theseriff/jobify/actions/workflows/pr_tests.yml)
[![Coverage](https://coverage-badge.samuelcolvin.workers.dev/theseriff/jobify.svg)](https://coverage-badge.samuelcolvin.workers.dev/redirect/theseriff/jobify)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[**Documentation**](https://theseriff.github.io/jobify/) •
[**Quick Start**](#quick-start) •
[**Community Extensions**](https://github.com/Jobify-Community) •
[**Telegram**](https://t.me/jobify_community)

</div>

## Contents

- [Why Jobify](#why-jobify)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Key Features](#key-features)
- [When to Choose Jobify](#when-to-choose-jobify)
- [Roadmap](https://github.com/theseriff/jobify/issues/107)
- [License](#license)

## Why Jobify

Most Python schedulers rely on polling loops. Jobify uses low-level `asyncio` timers (`call_at`) to schedule jobs directly.

- **No idle polling CPU cost**
- **Sub-millisecond trigger precision**
- **Native async-first execution model**

If your workload is bursty or downstream services are sensitive, use [Queue Middleware](https://theseriff.github.io/jobify/advanced_usage/queue/) to add bounded buffering, backpressure, and priority routing.

## Installation

```bash
pip install jobify
```

## Quick Start

```python
import asyncio

from jobify import Jobify

app = Jobify()


@app.task
async def hello(name: str) -> None:
    print(f"Hello, {name}")


async def main() -> None:
    async with app:
        job = await hello.push("Alex")
        await job.wait()


if __name__ == "__main__":
    asyncio.run(main())
```

<details>
<summary>Extended example (cron, delay, absolute time)</summary>

```python
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jobify import Jobify

UTC = ZoneInfo("UTC")
app = Jobify(tz=UTC)


@app.task(cron="* * * * * * *")  # every second
async def my_cron() -> None:
    print("cron tick")


@app.task
def my_job(name: str) -> None:
    now = datetime.now(tz=UTC)
    print(f"Hello, {name}! at {now!r}")


async def main() -> None:
    async with app:
        await my_job.push("Alex")

        run_next_day = datetime.now(tz=UTC) + timedelta(days=1)
        job_at = await my_job.schedule("Connor").at(run_next_day)
        job_delay = await my_job.schedule("Sara").delay(seconds=20)
        job_cron = await my_cron.schedule().cron("* * * * *", job_id="dynamic_cron_id")

        await job_at.wait()
        await job_delay.wait()
        await job_cron.wait()


if __name__ == "__main__":
    asyncio.run(main())
```

</details>

## Key Features

- [**Precision scheduling**](https://theseriff.github.io/jobify/#why-jobify): event-driven timers, no polling loop.
- [**Flexible triggers**](https://theseriff.github.io/jobify/schedule/): now, delay, timestamp, cron.
- [**Persistence**](https://theseriff.github.io/jobify/app_settings/#storage): built-in SQLite storage for scheduled jobs.
- [**Routing**](https://theseriff.github.io/jobify/router/): organize tasks with `JobRouter`.
- [**Context injection**](https://theseriff.github.io/jobify/context/): inject state and dependencies into tasks.
- [**Middleware pipeline**](https://theseriff.github.io/jobify/app_settings/#middleware): execution and scheduling interceptors.
- [**Queue middleware**](https://theseriff.github.io/jobify/advanced_usage/queue/): FIFO/LIFO/PriorityQueue with backpressure.
- [**Exception handlers**](https://theseriff.github.io/jobify/advanced_usage/exception_handlers/): hierarchical error handling.
- [**Run modes**](https://theseriff.github.io/jobify/task_settings/#run_mode): `asyncio`, thread pool, process pool.
- [**Community DB adapters**](https://github.com/Jobify-Community/jobify-db).

<details>
<summary>Feature comparison (Jobify vs Taskiq/APScheduler/Celery)</summary>

| Feature name                                                                                    |        Jobify        |      Taskiq       | APScheduler (v3) |      Celery       |
| :---------------------------------------------------------------------------------------------- | :------------------: | :---------------: | :--------------: | :---------------: |
| **Event-driven Scheduling**                                                                     | ✅ (Low-level timer) | ❌ (Polling/Loop) |  ❌ (Interval)   | ❌ (Polling/Loop) |
| **Async Native (asyncio)**                                                                      |          ✅          |        ✅         | ❌ (Sync mostly) |        ❌         |
| [**Context Injection**](https://theseriff.github.io/jobify/context/)                            |          ✅          |        ✅         |        ❌        |        ❌         |
| [**FastAPI-style Routing**](https://theseriff.github.io/jobify/router/)                         |          ✅          |        ❌         |        ❌        |        ❌         |
| [**Middleware Support**](https://theseriff.github.io/jobify/app_settings/#middleware)           |          ✅          |        ✅         | ❌ (Events only) |   ❌ (Signals)    |
| [**Lifespan Support**](https://theseriff.github.io/jobify/app_settings/#lifespan)               |          ✅          |        ✅         |        ❌        |        ❌         |
| [**Exception Handlers**](https://theseriff.github.io/jobify/advanced_usage/exception_handlers/) |  ✅ (Hierarchical)   |        ❌         |        ❌        |        ❌         |
| [**Job Cancellation**](https://theseriff.github.io/jobify/job/#await-jobcancel)                 |          ✅          |        ❌         |        ✅        |        ✅         |
| [**Cron Scheduling**](https://theseriff.github.io/jobify/schedule/#cron-expressions)            |  ✅ (Seconds level)  |   ✅ (Minutes)    |        ✅        |        ✅         |
| [**Misfire Policy**](https://theseriff.github.io/jobify/schedule/#the-cron-object)              |          ✅          |        ❌         |        ✅        |        ❌         |
| [**Run Modes (Thread/Process)**](https://theseriff.github.io/jobify/task_settings/#run_mode)    |          ✅          |        ✅         |        ✅        |        ✅         |
| **Zero-config Persistence**                                                                     | ✅ (SQLite default)  | ❌ (Needs Broker) |        ✅        | ❌ (Needs Broker) |
| **Broker-backend execution**                                                                    |     ❌ (roadmap)     |        ✅         |        ❌        |        ✅         |

</details>

## When to Choose Jobify

Use Jobify when:

- you need precise in-process scheduling without polling overhead
- you want typed, framework-like APIs for task registration and routing
- you need queue-based backpressure and priority controls in a single process

## License

This project is licensed under the [MIT license](https://github.com/theseriff/jobify/blob/main/LICENSE).
