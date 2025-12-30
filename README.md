# Jobber

[![Run all tests](https://github.com/suiseriff/jobber/actions/workflows/pr_tests.yml/badge.svg)](https://github.com/suiseriff/jobber/actions/workflows/pr_tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

**Jobber** is a robust solution that was built from the ground up to handle asynchronous tasks. It offers a clean and modern API that is inspired by leading frameworks.

## Key features

- **Routing**: There are routers like in fastAPI/Starlette/Aiogram.
- **Schedule**: For cron, add two extra optional fields, `* * * * * * *`, for the second interval.
- **Lifespan**: The lifespan of the application is similar to that of FastAPI/Starlette.
- **Middleware**: Middleware such as fastAPI/Starlette/Aiogram.
- **Exception Handling**: Exception handling using fastAPI/Starlette.

---

## Quick Start

Install Jobber from PyPI:
```bash
pip install jobber
```

Here is a simple example of how to schedule and run a job:

```python
import asyncio
from datetime import datetime, timezone
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

        await job_at.wait()
        await job_delay.wait()

        # Or
        # It is blocked indefinitely because the cron has infinite planning.
        await app.wait_all()


if __name__ == "__main__":
    asyncio.run(main())
```
