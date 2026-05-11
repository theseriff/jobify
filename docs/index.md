# Jobify

**Jobify** is an asynchronous job scheduling framework for Python with event-driven timers, typed APIs, and production-focused execution controls.

<div class="grid cards" markdown>

- :material-timer-outline:{ .lg .middle } **Event-driven Precision**

    ***

    Low-level `asyncio` timers instead of polling. Run now, after delay, at timestamp, or via cron.

    [:octicons-arrow-right-24: Why Jobify](#why-jobify){ data-preview }

- :material-database-lock:{ .lg .middle } **Built-in Persistence**

    ***

    SQLite storage keeps scheduled jobs across restarts. Durable by default, with easy opt-out.

    [:octicons-arrow-right-24: Open Storage](app_settings.md#storage){ data-preview }

- :material-sort-variant-lock:{ .lg .middle } **Queue + Backpressure**

    ***

    Control throughput with bounded queues, concurrent workers, and priority-based routing.

    [:octicons-arrow-right-24: Open Queue Middleware](advanced_usage/queue.md){ data-preview }

- :material-shield-alert-outline:{ .lg .middle } **Reliable Architecture**

    ***

    FastAPI-style routing, lifespans, and hierarchical exception handlers for robust apps.

    [:octicons-arrow-right-24: Open Router](router.md){ data-preview }

</div>

## Comparison

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

## Why Jobify?

Jobify uses `asyncio.loop.call_at` instead of polling loops.

1. **Efficiency:** No idle CPU usage when nothing is scheduled.
2. **Precision:** Sub-millisecond timing without polling jitter.
3. **Native behavior:** Works with OS event-notification primitives.

!!! note "Precision vs Polling Trade-off"
    Event-driven scheduling is sensitive to significant system clock shifts.
    See [System Time and Scheduling](advanced_usage/system_time.md){ data-preview }.

## Quick Start

### Installation

```bash
pip install jobify
```

### Basic Usage

```python linenums="1" hl_lines="11 16 24 27-29"
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
        job_delay = await my_job.schedule("Sara").delay(20)
        job_cron = await my_cron.schedule().cron("* * * * *", job_id="dynamic_cron_id")

        await job_at.wait()
        await job_delay.wait()
        await job_cron.wait()


if __name__ == "__main__":
    asyncio.run(main())
```
