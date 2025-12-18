# Jobber

[![Run all tests](https://github.com/suiseriff/jobber/actions/workflows/pr_tests.yml/badge.svg)](https://github.com/suiseriff/jobber/actions/workflows/pr_tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

**Jobber** is a good program for doing things behind the scenes in Python. You can use it to make a lot of things happen at the same time. It has a good architecture for making, doing, and keeping jobs. It can work with different engines, middlewares, and ways to save things.

Jobber is strong and made to do things that don't happen together. It has an easy and new API like other good programs.

## Features

- **Schedule**: Jobber can run jobs on a schedule. You can use an extra field for seconds to run jobs very often.
- **Dependencies**: Job can use things from other places.
- **When it starts and stops**: Job can do things when it starts and when it stops. This is good for things like connecting to a database.
- **Extra things**: Job can have extra things done before or after it runs. This is useful for things like writing to a log or checking if a user is logged in.
- **Exception Handling**: Don't let your app crash because of one bad job. Make your own exceptions for different mistakes. You can write down the mistake, do the job again, or tell the programmer.
- **Time Zones**: Let's not worry about time zones. We can make jobs for people in different places. With Jobber, you can make a job for any time and change time zones.

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
