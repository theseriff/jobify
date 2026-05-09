# Jobify Configuration

`Jobify(...)` accepts a set of constructor arguments that control scheduling behavior, persistence, middleware, and execution strategy.

<div class="grid cards" markdown>

- :material-cog-outline:{ .lg .middle } **Core Runtime**

    ***

    Time zone, state, serializer, storage, loop, cron parser.

- :material-layers-triple-outline:{ .lg .middle } **Execution Pipeline**

    ***

    Middleware, outer middleware, exception handlers, worker pools.

- :material-puzzle-outline:{ .lg .middle } **Extensibility**

    ***

    Custom route class, plugins, dumper/loader integration hooks.

- :material-account-hard-hat:{ .lg .middle } **Worker Pools**

    ***

    Custom thread and process executors for optimized sync workload isolation.

</div>

## Constructor Snapshot

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from zoneinfo import ZoneInfo

from jobify import Jobify, Plugin
from jobify.crontab import create_crontab
from jobify.middleware import QueueMiddleware
from jobify.router import RootRoute
from jobify.serializers import JSONSerializer
from jobify.storage import SQLiteStorage

app = Jobify(
    tz=ZoneInfo("UTC"),
    state=None,
    dumper=None,
    loader=None,
    storage=SQLiteStorage(),
    lifespan=None,
    serializer=JSONSerializer(),
    middleware=[QueueMiddleware()],
    outer_middleware=[],
    cron_factory=create_crontab,
    loop_factory=asyncio.get_running_loop,
    exception_handlers={},
    threadpool_executor=ThreadPoolExecutor(max_workers=8),
    processpool_executor=ProcessPoolExecutor(max_workers=4),
    route_class=RootRoute,
    plugins=(),
)
```

!!! note "Storage behavior"
    `storage=None` is not used as a constructor option now; default behavior is already `SQLiteStorage()`.
    To disable persistence, use `storage=False`.

## tz

- **Type**: `zoneinfo.ZoneInfo | None`
- **Default**: `zoneinfo.ZoneInfo("UTC")`

Defines the application time zone used for scheduling and cron calculations.

## state

- **Type**: `State | None`
- **Default**: `None`

Initial state container passed into the app/router state system.
Use this when you want pre-populated mutable state before startup hooks run.

## dumper and loader

- **Type**: `Dumper | None`, `Loader | None`
- **Default**: `DummyDumper()`, `DummyLoader()`

Integration hooks for custom type conversion.

- `dumper`: converts Python objects to storable payloads.
- `loader`: restores payloads back to Python objects.

Typical use cases: `adaptix`, `pydantic`, custom domain objects.

## storage

- **Type**: `Storage | Literal[False]`
- **Default**: `SQLiteStorage()`

Controls persistence for scheduled jobs.

=== "SQLite (recommended default)"

    ```python
    from jobify import Jobify

    app = Jobify()  # SQLiteStorage() is used automatically
    ```

=== "Disable persistence"

    ```python
    from jobify import Jobify

    app = Jobify(storage=False)  # in-memory only
    ```

=== "Custom backend"

    ```python
    from jobify import Jobify
    from jobify.storage import Storage

    class MyStorage(Storage):
        ...

    app = Jobify(storage=MyStorage())
    ```

## lifespan

- **Type**: `Lifespan[Jobify] | None`
- **Default**: `None`

Async context manager for startup/shutdown lifecycle, similar to FastAPI lifespan.
You can yield a dictionary-like state that becomes available through `app.state`.

```python
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from jobify import Jobify


class AppState(TypedDict):
    db: object
    cache: dict[str, str]


@asynccontextmanager
async def lifespan(_: Jobify) -> AsyncIterator[AppState]:
    db = object()
    yield {"db": db, "cache": {}}


async def main() -> None:
    async with Jobify(lifespan=lifespan) as app:
        assert "db" in app.state


if __name__ == "__main__":
    asyncio.run(main())
```

## serializer

- **Type**: `Serializer | None`
- **Default**: `ExtendedJSONSerializer` or `JSONSerializer`

Primary serializer for message payloads.

- If `dumper` and `loader` are both `None`, Jobify uses `ExtendedJSONSerializer`.
- If custom dumper/loader are provided, it falls back to `JSONSerializer` unless serializer is explicitly passed.

## middleware

- **Type**: `Sequence[BaseMiddleware] | None`
- **Default**: `None`

Execution middleware chain for job runtime behavior (retry-like logic, logging, auth checks, queueing).

```python
import asyncio
import logging
from typing import Any

from jobify import JobContext, Jobify
from jobify.middleware import BaseMiddleware, CallNext

logging.basicConfig(level=logging.INFO)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, call_next: CallNext, context: JobContext) -> Any:
        logging.info("Job %s started", context.job.id)
        try:
            return await call_next(context)
        finally:
            logging.info("Job %s finished", context.job.id)


app = Jobify(middleware=[LoggingMiddleware()])
```

If middleware does not call `call_next(context)`, execution is skipped and the returned value is treated as the job result.

## outer_middleware

- **Type**: `Sequence[BaseOuterMiddleware] | None`
- **Default**: `None`

Runs on scheduling operations (`.push()`, `.schedule().delay/at/cron`) instead of execution.
Useful for scheduling-time policies, argument normalization, and schedule audit logging.

```python
import asyncio

from jobify import Jobify, OuterContext
from jobify.middleware import BaseOuterMiddleware, CallNextOuter


class ScheduleLoggerMiddleware(BaseOuterMiddleware):
    async def __call__(self, call_next: CallNextOuter, context: OuterContext) -> asyncio.Handle:
        print(f"Scheduling {context.job.id} with trigger={context.trigger}")
        return await call_next(context)


app = Jobify(outer_middleware=[ScheduleLoggerMiddleware()])
```

!!! warning "Execution condition"
    By default, outer middleware runs only when a schedule is created or changed.
    Use `force=True` if you need execution on every scheduling call regardless of idempotent state.

## cron_factory

- **Type**: `CronFactory`
- **Default**: `jobify.crontab.create_crontab`

Factory for cron expression parsing.
Override this if you need custom parser behavior or deterministic testing.

## loop_factory

- **Type**: `LoopFactory`
- **Default**: `asyncio.get_running_loop`

Callable returning the event loop used by the application.

## exception_handlers

- **Type**: `MappingExceptionHandlers | None`
- **Default**: `None`

Global exception handler mapping for task failures.

[Read exception handlers guide](advanced_usage/exception_handlers.md){ data-preview }

## threadpool_executor and processpool_executor

- **Type**: `ThreadPoolExecutor | None`, `ProcessPoolExecutor | None`
- **Default**: `None`

Custom executors for sync workloads:

- `threadpool_executor`: IO-bound sync functions.
- `processpool_executor`: CPU-bound sync functions.

If omitted, Jobify creates/manages worker pools automatically.

## route_class

- **Type**: `type[RootRoute[..., Any]]`
- **Default**: `jobify.router.RootRoute`

Advanced override for task route behavior.
Use this when implementing custom execution wrappers, DI integration, or route instrumentation.

## plugins

- **Type**: `Sequence[Plugin]`
- **Default**: `()`

Registers app lifecycle plugins (`startup`/`shutdown` hooks).
Middleware objects implementing `Plugin` are also auto-collected during startup.

```python
from jobify import Jobify, Plugin


class MyPlugin(Plugin):
    async def startup(self, app: Jobify) -> None:
        print("plugin startup")

    async def shutdown(self) -> None:
        print("plugin shutdown")


app = Jobify(plugins=[MyPlugin()])
```
