# Routers

`JobRouter` allows you to organize tasks into logical groups, much like FastAPI's `APIRouter`. This modular approach is essential for scaling applications, enabling better separation of concerns and easier maintenance.

<div class="grid cards" markdown>

- :material-file-tree:{ .lg .middle } **Modularization**

    ***

    Split your application into domain-specific modules (e.g., `email`, `billing`, `analytics`).

- :material-label-outline:{ .lg .middle } **Hierarchical Naming**

    ***

    Automatic prefixing ensures task names are unique and easily searchable.

- :material-cog-box:{ .lg .middle } **Scoped Config**

    ***

    Apply middleware, exception handlers, and lifespans to specific groups of tasks.

- :material-package-variant-closed:{ .lg .middle } **Encapsulation**

    ***

    Keep related tasks and their dependencies together in a single, reusable unit.

</div>

## Basic Usage

To use routers, define tasks on a `JobRouter` and then include it in your main `Jobify` application.

=== "1. Define tasks (`tasks/email.py`)"

    ```python
    from jobify import JobRouter

    router = JobRouter(prefix="email")

    @router.task
    async def send_welcome(user_id: int) -> None:
        print(f"Sending welcome to {user_id}")
    ```

=== "2. Register router (`main.py`)"

    ```python
    from jobify import Jobify
    from tasks.email import router as email_router
    from tasks.email import send_welcome

    app = Jobify()
    app.include_router(email_router)

    async def main():
        async with app:
            # Tasks are now active and schedulable
            await send_welcome.schedule(user_id=42).delay(0)
    ```

## Configuration

`JobRouter` accepts several parameters that apply to all contained tasks and nested sub-routers.

| Parameter            | Type                        | Description                                          |
| -------------------- | --------------------------- | ---------------------------------------------------- |
| `prefix`             | `str`                       | String prepended to all task names in this router.   |
| `state`              | `dict`                      | Initial local state for the router.                  |
| `lifespan`           | `AsyncContextManager`       | Async generator for startup/shutdown events.         |
| `middleware`         | `Sequence`                  | Execution-phase middlewares.                         |
| `outer_middleware`   | `Sequence`                  | Scheduling-phase middlewares.                        |
| `exception_handlers` | `dict`                      | Mapping of exception types to handlers.              |
| `route_class`        | `type[NodeRoute]`           | Custom class for task handling (default: `NodeRoute`). |

## Nesting & Prefixes

Routers can be nested to create complex hierarchies. Prefixes are joined by dots (`.`), while the final task name is separated by a colon (`:`).

```python
# reports/router.py (prefix="reports")
# reports/daily.py  (prefix="daily", nested in reports)

@daily_router.task(name="generate")
def gen(): ...

# Resulting name: "reports.daily:generate"
```

!!! info "Naming Logic"
    The final task ID follows the pattern: `[parent_prefix].[sub_prefix]:[task_name]`. This hierarchy makes it clear where a task originates during debugging or monitoring.

## Router-level Lifespan

Use router lifespans to manage resources specific to a module, such as a specialized database connection.

```python
@asynccontextmanager
async def reports_lifespan(router: JobRouter) -> AsyncIterator[None]:
    router.state["db"] = await connect_to_reports_db()
    yield
    await router.state["db"].close()

reports_router = JobRouter(prefix="reports", lifespan=reports_lifespan)
```

!!! warning "Detached Routers"
    Attempting to schedule a task from a router that has not been included in a `Jobify` application will raise a `RuntimeError`. A router must be attached to an app instance to access the scheduling engine.
