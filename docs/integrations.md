# Integrations

Jobify is built with a focus on extensibility, making it easy to integrate with your favorite frameworks, dependency injection systems, and database backends.

<div class="grid cards" markdown>

- :material-puzzle-outline:{ .lg .middle } **Dependency Injection**

    ***

    Seamlessly connect with frameworks like Dishka for robust, typed DI in your tasks.

- :material-database-plus:{ .lg .middle } **Expanded Storage**

    ***

    Use community-supported drivers to persist jobs in Redis, PostgreSQL, and more.

- :material-api:{ .lg .middle } **ASGI Native**

    ***

    First-class support for FastAPI, Starlette, and other ASGI lifespans.

- :material-plus-circle-outline:{ .lg .middle } **Custom Extensions**

    ***

    Easily build your own plugins or middleware to extend core functionality.

</div>

## [Dishka](https://github.com/reagento/dishka)

[dishka-jobify](https://github.com/Jobify-Community/dishka-jobify) connects Jobify with **Dishka**, a modern Python dependency injection framework. It allows you to inject providers directly into your task functions using the standard `INJECT` pattern.

## [jobify-db](https://github.com/Jobify-Community/jobify-db)

[jobify-db](https://github.com/Jobify-Community/jobify-db) expands Jobify's persistence layer with additional database backends. This is the recommended package if you need to move beyond the default SQLite storage.

## FastAPI & ASGI Frameworks

Frameworks that support the ASGI lifespan protocol (like FastAPI or Starlette) don't require a dedicated integration package. You can manage the `Jobify` lifecycle directly within your app's lifespan handler.

=== "Lifespan (Recommended)"

    Use the `async with` context manager to automatically handle startup and shutdown.

    ```python
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from jobify import Jobify

    jobify_app = Jobify()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with jobify_app:
            yield

    app = FastAPI(lifespan=lifespan)
    ```

=== "Manual Startup/Shutdown"

    If you need more granular control, you can call the lifecycle methods explicitly.

    ```python
    from fastapi import FastAPI
    from jobify import Jobify

    jobify_app = Jobify()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await jobify_app.startup()
        yield
        await jobify_app.shutdown()

    app = FastAPI(lifespan=lifespan)
    ```

!!! tip "Looking for more?"
    If you've built an integration for Jobify, feel free to open a PR to add it to this list!
