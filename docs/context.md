# JobContext

`JobContext` is a special object that holds all the information related to the current job.
It is used by handlers and middleware to access the job's state, configuration, and other important data.

It serves as a central component that connects various parts of the process during its execution.

## Why is it needed?

Using `JobContext` allows for:

1. **State Isolation**: Each job execution receives its own context, preventing state conflicts between concurrently running jobs.
2. **Simplified Data Access**: Instead of passing numerous arguments to functions, all necessary data is gathered in a single object. This simplifies function signatures and improves code readability.
3. **Extensibility**: Middleware can modify the context or use its data to implement additional logic, such as logging, error handling, caching, etc.

## `JobContext` Attributes

`JobContext` is a dataclass with the following attributes, giving middleware and injected functions complete insight into the execution environment.

- `job: Job[Any]`: Contains live information about the task being executed, such as its ID, status, and metadata.
- `state: State`: Represents the global `app.state`. This is a shared dictionary where you can store anything, including resources initialized via the `lifespan` manager (like database connections). It's accessible across all jobs.
- `runnable: Runnable[Any]`: An internal object that holds the execution strategy for the job's function, along with its bound arguments (`inspect.BoundArguments`).
- `request_state: RequestState`: A temporary state object that exists _only_ for the duration of a single job execution. Middleware can use it to dynamically add attributes and pass data to subsequent middleware or even to the final job function.
- `route_options: RouteOptions`: The configuration options passed to the task decorator itself, e.g., `timeout`, `retry`, and other settings from `@app.task(**options)`.
- `jobify_config: JobifyConfiguration`: The main `Jobify` application configuration object, containing all global settings passed to the `Jobify(...)` constructor.

## Context Injection

While middleware has direct access to the `JobContext`, your job function can also access it, or parts of it, through dependency injection. This is the recommended way to get execution information within your task.

To do this, you can declare a parameter in your job function, type-hint it with the object you need, and assign it the special default value `INJECT`.

### Injecting the Full `JobContext`

If you need access to multiple context attributes, you can inject the entire `JobContext` object.

```python
from jobify import INJECT, Jobify, JobContext

app = Jobify()

@app.task
def my_job(ctx: JobContext = INJECT) -> None:
    print(f"Executing job {ctx.job.id}")
    # Access other attributes like ctx.jobify_config, etc.
```

### Injecting Specific Attributes

If you only need a specific piece of information, like the `Job` object itself, you can inject it directly. This is cleaner and makes the function's dependencies more explicit.

```python
from jobify import INJECT, Job, Jobify

app = Jobify()

@app.task
def my_other_job(current_job: Job[None] = INJECT) -> None:
    print(f"Job ID: {current_job.id}")
```

You can inject any attribute of the `JobContext` by using its type hint (e.g., `Job`, `State`, `JobifyConfiguration`).

# OuterContext

`OuterContext` is similar to `JobContext`, but it is used exclusively during the scheduling phase by **outer middleware**.
It provides information about a job before it is registered with the scheduler or persisted in the database.

## `OuterContext` Attributes

- `job: Job[Any]`: The job object that is being scheduled.
- `trigger: AtArguments | CronArguments`: Details of the scheduling trigger (e.g., specific time or cron expression).
- `runnable: Runnable[Any]`: The internal runnable object.
- `arguments: dict[str, Any]`: Arguments passed to the job function.
- `func_spec: FuncSpec[Any]`: Metadata about the job function (signature, etc.).
- `is_force: bool`: Whether `force=True` was passed as an argument.
- `is_persist: bool`: Whether the job should be persisted to storage.
- `is_replace: bool`: Whether `replace=True` was passed as an argument.
- `state: State`: The global application state.
- `route_options: RouteOptions`: Configuration options for the route.
- `jobify_config: JobifyConfiguration`: Global application configuration.
- `request_state: RequestState`: A temporary object used during the scheduling process.
