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
- `jobber_config: JobberConfiguration`: The main `Jobber` application configuration object, containing all global settings passed to the `Jobber(...)` constructor.

## Context Injection

While middleware has direct access to the `JobContext`, your job function can also access it, or parts of it, through dependency injection. This is the recommended way to get execution information within your task.

To do this, you can declare a parameter in your job function, type-hint it with the object you need, and assign it the special default value `INJECT`.

### Injecting the Full `JobContext`

If you need access to multiple context attributes, you can inject the entire `JobContext` object.

```python
from jobber import INJECT, Jobber, JobContext

app = Jobber()

@app.task
def my_job(ctx: JobContext = INJECT) -> None:
    print(f"Executing job {ctx.job.id}")
    # Access other attributes like ctx.jobber_config, etc.
```

### Injecting Specific Attributes

If you only need a specific piece of information, like the `Job` object itself, you can inject it directly. This is cleaner and makes the function's dependencies more explicit.

```python
from jobber import INJECT, Job, Jobber

app = Jobber()

@app.task
def my_other_job(current_job: Job[None] = INJECT) -> None:
    print(f"Job ID: {current_job.id}")
```

You can inject any attribute of the `JobContext` by using its type hint (e.g., `Job`, `State`, `JobberConfiguration`).
