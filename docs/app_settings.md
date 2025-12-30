# Jobber Configuration

These arguments are passed to the `Jobber` class instance.

```python
import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from adaptix import Retort

from jobber import Jobber
from jobber.crontab import create_crontab
from jobber.serializers import JSONSerializer
from jobber.storage import SQLiteStorage


@asynccontextmanager
async def mylifespan(_: Jobber) -> AsyncIterator[None]:
    yield None


app = Jobber(
    tz=ZoneInfo("UTC"),
    dumper=Retort(),
    loader=Retort(),
    storage=SQLiteStorage(),
    lifespan=mylifespan,
    serializer=JSONSerializer(),
    middleware=[],
    cron_factory=create_crontab,
    loop_factory=asyncio.get_running_loop,
    exception_handlers={},
    threadpool_executor=ThreadPoolExecutor(max_workers=4),
    processpool_executor=ProcessPoolExecutor(max_workers=3),
)
```

## `tz`

- **Type**: `zoneinfo.ZoneInfo | None`
- **Default**: `zoneinfo.ZoneInfo("UTC")`

Sets the default time zone for the application.
Any time-related calculations (such as for cron jobs) will use this time zone unless a different time zone is specified for a specific job.

## `dumper` and `loader`

- **Type**: `Dumper | None`, `Loader | None`
- **Default**: `DummyDumper`, `DummyLoader`

These are hooks for integrating with external type systems or advanced serialization libraries, such as `adaptix` and `pydantic`.

- `dumper`: A function or object that converts complex data types into a format that can be stored in a file or database, and is not handled by the main serializer.
- `loader`: A function or object that reads the data from a file or database and converts it back into Python objects.

By default, they do nothing.

## `storage`

- **Type**: `Storage | Literal[False] | None`
- **Default**: `None`

Configures the persistence layer for jobs.

- **`None` (default)**: Uses `SQLiteStorage`, which saves jobs to a local SQLite database file (`jobber.sqlite`). This is the recommended option for single-node storage.
- **`False`**: Uses `DummyStorage`, which is an in-memory storage. Jobs are not saved and will be lost if the application is restarted.
- **Custom Storage**: You can provide an instance of a class that implements the `jobber._internal.storage.abc.Storage` abstract base class to customize the persistence logic (for example, using a different database).

## `lifespan`

- **Type**: `Lifespan[Jobber] | None`
- **Default**: `None`

An async context manager for executing code during application startup and shutdown,
working just like [FastAPI's lifespan events](https://fastapi.tiangolo.com/advanced/events/).
This is useful for managing resources, such as database connections or external clients.

You can use `yield` to pass a dictionary to the state of the app.
This state will be accessible through `app.state`, for example `app.state.database` or `app.state.cache`.

Example:

```python
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, NewType, TypedDict

from jobber import Jobber

Cache = NewType("Cache", dict[str, Any])
Database = NewType("Database", dict[str, Any])


class State(TypedDict):
    pool: Database
    cache: Cache


@asynccontextmanager
async def lifespan(app: Jobber) -> AsyncIterator[State]:
    print("Application starting up!")
    # e.g., initialize database connections
    db = Database({})
    # The yielded dictionary will be stored in app.state
    yield {"database": db, "cache": Cache({})}
    print("Application shutting down!")
    # e.g., close connections gracefully


app = Jobber(lifespan=lifespan)


async def main() -> None:
    async with app:
        # app.state.database is now accessible.
        print("Application running with state:", app.state)


if __name__ == "__main__":
    asyncio.run(main())
```

## `serializer`

- **Type**: `Serializer | None`
- **Default**: `ExtendedJSONSerializer` or `JSONSerializer`

The primary serializer for converting job data, such as function arguments, into a storable format.

- If `dumper` and `loader` are not specified, the default value is `ExtendedJSONSerializer`, which supports common types such as `datetime`.
- Otherwise, it will fall back to the simpler `JSONSerializer`.
- You can provide your own custom serializer instance that implements the `jobber._internal.serializers.base.Serializer` interface.

## `middleware`

- **Type**: `Sequence[BaseMiddleware] | None`
- **Default**: `None`

A sequence of middleware that can be applied globally to all jobs. The middleware can intercept job execution and add features such as automatic retries, timeouts, or custom logging.

Example:

```python
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from jobber import Jobber
from jobber._internal.context import JobContext
from jobber._internal.middleware.base import BaseMiddleware

logging.basicConfig(level=logging.INFO)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        call_next: Callable[[JobContext], Awaitable[Any]],
        context: JobContext,
    ) -> Any:
        logging.info("Job %s is starting.", context.job.id)
        try:
            return await call_next(context)
        finally:
            logging.info("Job %s has finished.", context.job.id)


app = Jobber(middleware=[LoggingMiddleware()])


@app.task
def my_task() -> None:
    print("Hello from my_task!")


async def main() -> None:
    async with app:
        job = await my_task.schedule().delay(0.1)
        await job.wait()  # wait for task to run


if __name__ == "__main__":
    asyncio.run(main())
```

When you run this code, you will see output similar to this:

```
INFO:root:Job 1922a07f509e4ae098bd8ff4ebca2830 is starting.
Hello from my_task!
INFO:root:Job 1922a07f509e4ae098bd8ff4ebca2830 has finished.
```

A crucial feature of middleware is its ability to control the order in which functions are executed.
The `call_next(context)` function call allows the middleware to move on to the next step in the process,
or to execute the job function directly if it is the last step.

If a middleware decides **not to call `call_next`** and returns a value instead,
the execution of the job (and any subsequent processes) is gracefully skipped.
This allows for powerful features, such as the ability to implement custom authorization checks that can prevent a job from running.

For example, this middleware will skip any job that has `skip: True` in its metadata.

```python
class SkipMiddleware(BaseMiddleware):
    async def __call__(
        self,
        call_next: Callable[[JobContext], Awaitable[Any]],
        context: JobContext,
    ) -> Any:
        if context.job.metadata.get("skip") is True:
            logging.warning("Job %s was skipped by middleware.", context.job.id)
            return None  # Do not call call_next, stopping execution

        return await call_next(context)
```

## `cron_factory`

- **Type**: `CronFactory | None`
- **Default**: `jobber.crontab.create_crontab`

A factory function for parsing cron expression strings, which supports the standard cron syntax by default, with an optional field for seconds.

## `loop_factory`

- **Type**: `LoopFactory`
- **Default**: `asyncio.get_running_loop`

A callable that returns an `asyncio` event loop for the application to use.

## `exception_handlers`

- **Type**: `MappingExceptionHandlers | None`
- **Default**: `None`

A dictionary that maps exception types to custom error handling functions, allowing for more fine-grained and customized error handling when jobs fail.

## `threadpool_executor` and `processpool_executor`

- **Type**: `ThreadPoolExecutor | None`, `ProcessPoolExecutor | None`
- **Default**: `None`

Executors for running tasks in separate threads or processes.

- `threadpool_executor`: To run synchronous, I/O-bound functions without blocking the main `asyncio` event loop.
- `processpool_executor`: This is used for running synchronous, CPU-intensive functions in a separate process in order to avoid blocking the main event loop and the Global Interpreter Lock (GIL).

If not specified, `Jobber` will automatically create and manage executors as needed.
