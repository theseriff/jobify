# Routers

Routers are a useful tool for organizing tasks into logical groups in your application.
If you have a large number of tasks, you can divide them into different Python modules using routers.
This is similar to how web frameworks such as FastAPI and aiogram handle routing.

This approach leads to a more organized code structure, better separation of responsibilities, and easier maintenance.

## Basic Usage

First, create a `JobRouter` instance. A router is a mini-application that can define its own tasks, middleware, and lifecycle events.

```python
# in tasks/email.py
from jobber import JobRouter

router = JobRouter()


@router.task
async def send_welcome_email(user_id: int) -> None:
    print(f"Sending welcome email to user {user_id}")
```

This task is currently registered with the `router`, but it is not yet active.
In order to make it available for scheduling, you will need to include the router in your main `Jobber` application.

```python
# in main.py
from tasks.email import router as email_router
from tasks.email import send_welcome_email

from jobber import Jobber


async def main() -> None:
    app = Jobber()
    # Include the router in the main app
    app.include_router(email_router)
    async with app:
        # Now you can schedule tasks defined on the router
        job = await send_welcome_email.schedule(user_id=123).delay(0)
        await job.wait()
# ...
```

## Organizing with Prefixes and Nesting

Routers can be nested within each other, and each router can have a `prefix`.
Prefixes automatically combine to create a unique hierarchical name for each route,
which helps avoid naming conflicts as your application grows.

### Prefixes

You can specify a `prefix` when creating a router.
This prefix will be added to the names of all tasks and subrouters that are registered under it.

```python
# in tasks/reports.py
from jobber import JobRouter

# This prefix will apply to all tasks in this router
router = JobRouter(prefix="reports")


@router.task
def generate_daily_report() -> None: ...


@router.task(func_name="weekly")  # You can also specify a custom name
def generate_weekly_report() -> None: ...
```

If you include this router in your app, the tasks will have the following names:

- `reports:generate_daily_report`
- `reports:weekly`

### Nested Routers

You can build complex task hierarchies by including routers within other routers using `include_router()` or `include_routers()`.

```python
# in services/analytics.py
from jobber import JobRouter

# Sub-router for user-related analytics
users_router = JobRouter(prefix="users")

@users_router.task
def track_logins() -> None: ...


# Main router for the analytics service
analytics_router = JobRouter(prefix="analytics")
analytics_router.include_router(users_router)

# in main.py
from jobber import Jobber
from services.analytics import analytics_router

app = Jobber()
app.include_router(analytics_router)
```

In the example above, the `track_logins` task will have the final resolved name `analytics.users:track_logins`.
The prefixes are separated by a dot (`.`) for sub-routers, and the final path is separated from the function name by a colon (":").

## Scheduling Tasks from Routers

As shown in the first example, you can only schedule a task on a router after that router has been added to the main `Jobber` application.

Attempting to schedule a task from a detached router will result in a `RuntimeError`.

```python
import pytest
from jobber import Jobber, JobRouter

router = JobRouter()

@router.task
async def my_task() -> None: ...

# This will fail!
# The router is not attached to any app yet.
with pytest.raises(RuntimeError):
    _ = my_task.schedule()

# Correct way:
app = Jobber()
app.include_router(router)

# Now, this will work:
async with app:
    job = await my_task.schedule().delay(0)
```

## Router-level Lifespan and Middleware

Just like the main `Jobber` app, each `JobRouter` can have its own `middleware` and `lifespan` events.

- **Middleware** applied to a parent router will also be applied to all of its sub-routers, in addition to any middleware they have defined.
- **Lifespan** events on a router can be useful for managing resources related to a specific group of tasks, such as connecting to a particular service.

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from jobber import Jobber, JobRouter

@asynccontextmanager
async def reports_lifespan(router: JobRouter) -> AsyncIterator[None]:
    print(f"'{router.prefix}' router is starting up!")
    # e.g., initialize a database connection and store it in the router's state
    router.state["db_conn"] = "..."
    yield
    print(f"'{router.prefix}' router is shutting down!")


reports_router = JobRouter(prefix="reports", lifespan=reports_lifespan)
# ... define tasks on reports_router ...

app = Jobber()
app.include_router(reports_router)
```

When the application starts, you will see a `starting up` message. All tasks within `reports_router` will have access to `router.state`.
