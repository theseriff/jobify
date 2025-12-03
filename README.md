# Jobber

[![Run all tests](https://github.com/suiseriff/jobber/actions/workflows/pr_tests.yml/badge.svg)](https://github.com/suiseriff/jobber/actions/workflows/pr_tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

**Jobber** is a powerful and flexible framework for scheduling and managing background tasks in Python. It offers a versatile architecture for defining, executing, and storing jobs, supporting a variety of execution engines, middleware, and serialization formats.

Jobber is a robust solution that was built from the ground up to handle asynchronous tasks. It offers a clean and modern API that is inspired by leading frameworks.

---

## Features

- **Middleware Support**: Jobber provides a flexible middleware processing pipeline, which allows you to add custom logic before or after a job is executed. This feature is similar to those found in frameworks like Starlette and aiogram, providing a powerful tool for customizing job execution.
- **Lifespan Events**: Effectively manage resources with startup and shutdown events. This is useful for initializing and cleaning up resources such as database connections.
- **Flexible Exception Handling**: Define custom exception handlers for different types of errors, allowing for more granular and flexible error-handling strategies.
- **Customizable Serialization**: Jobs can be saved in various formats. The default format is JSON, but you can also easily add your own custom serialization method to handle complex data types.
- **Full-Timezone Support**: Schedule jobs reliably for users in different regions, taking into account their local time zones.

---

## Quick Start

Install Jobber from PyPI:
```bash
pip install jobber
```

Here is a simple example of how to schedule and run a job:

```python
import asyncio
import datetime

from jobber import Jobber

# 1. Initialize Jobber
app = Jobber()


# 2. Define your function
@app.register
def my_job() -> None:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    print(f"Executing my_job at {now}")


async def main() -> None:
    # 4. Run the Jobber application context
    async with app:
        # 5. Schedule the job to run using a cron expression
        expression = "* * * * * * *"  # Runs every seconds
        job = await my_job.schedule().cron(expression)
        print(f"Job id: {job.id!r} with name: {job.name!r} scheduled.")

        await job.wait()
        await job.wait()
        # will run twice, then the application will terminate


if __name__ == "__main__":
    asyncio.run(main())
```
