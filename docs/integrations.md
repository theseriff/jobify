# Integrations

Jobify is designed to be extensible. Below are the community-supported and official integrations that enhance Jobify's capabilities.

## [Dishka](https://github.com/reagento/dishka)

[dishka-jobify](https://github.com/C3EQUALZz/dishka-jobify) is an integration library that connects Jobify with [Dishka](https://github.com/reagento/dishka), a Python dependency injection framework.

## [FastAPI](https://github.com/fastapi/fastapi)

FastAPI and other ASGI frameworks that support lifespan don't need a separate integration. Just add the code below to your lifespan or startup/shutdown handlers:

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

fastapi_app = FastAPI(lifespan=lifespan)
```

Or, using explicit startup/shutdown:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await jobify_app.startup()
    yield
    await jobify_app.shutdown()
```
