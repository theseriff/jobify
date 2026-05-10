# JobContext

`JobContext` is a specialized object that encapsulates the entire execution environment of a job. It serves as the single source of truth for handlers and middleware, providing access to job state, global configuration, and system resources.

<div class="grid cards" markdown>

- :material-shield-check:{ .lg .middle } **State Isolation**

    ***

    Each execution receives a fresh context, preventing state leakage or conflicts between concurrent jobs.

- :material-lightning-bolt:{ .lg .middle } **Simplified Access**

    ***

    Consolidates disparate data points into one object, keeping function signatures clean and readable.

- :material-puzzle-outline:{ .lg .middle } **Extensibility**

    ***

    Middleware can dynamically enrich the context with metadata, logging IDs, or cached resources.

- :material-check-decagram-outline:{ .lg .middle } **Type Safety**

    ***

    Fully type-hinted attributes ensure excellent IDE support and prevent runtime attribute errors.

</div>

## Context Attributes

`JobContext` provides complete insight into the execution lifecycle through the following attributes:

- :material-identifier: **`job`**: `Job[Any]` — Live information about the task (ID, status, metadata).
- :material-database: **`state`**: `State` — The global `app.state`, shared across all jobs (e.g., DB connections).
- :material-play-circle-outline: **`runnable`**: `Runnable[Any]` — Internal execution strategy and bound arguments.
- :material-Timer: **`request_state`**: `RequestState` — Temporary state existing only for the duration of this job.
- :material-cog: **`route_options`**: `RouteOptions` — Configuration from the `@app.task(...)` decorator.
- :material-tune: **`jobify_config`**: `JobifyConfiguration` — Global application settings.
- :material-calendar-range: **`schedule_builder`**: `ScheduleBuilder[Any]` — Access to internal scheduling state.

## Context Injection

While middleware has direct access to `JobContext`, your task functions can access it via **dependency injection**. Declare a parameter with the appropriate type hint and assign it the `INJECT` default value.

!!! note "The `INJECT` constant"
    Using `INJECT` signals to Jobify that the parameter should be resolved from the current execution context rather than from the arguments passed during scheduling.

=== "Injecting Full Context"

    Use this when you need access to multiple environment properties.

    ```python
    from jobify import INJECT, Jobify, JobContext

    app = Jobify()

    @app.task
    def my_job(ctx: JobContext = INJECT) -> None:
        print(f"Executing job {ctx.job.id}")
        # Access ctx.state, ctx.route_options, etc.
    ```

=== "Injecting Specifics"

    Declare exactly what you need for cleaner, more explicit dependencies.

    ```python
    from jobify import INJECT, Job, State, Jobify

    app = Jobify()

    @app.task
    def clean_task(current_job: Job[None] = INJECT, state: State = INJECT) -> None:
        print(f"Job ID: {current_job.id}")
        db = state["db"]
    ```

# OuterContext

`OuterContext` is the scheduling-phase counterpart to `JobContext`. It is used exclusively by **outer middleware** to inspect or modify a job *before* it is registered or persisted.

## Key Differences

| Feature          | JobContext           | OuterContext          |
| ---------------- | -------------------- | --------------------- |
| **Phase**        | Execution            | Scheduling            |
| **Availability** | Task & Middleware    | Outer Middleware Only |
| **Persistence**  | Post-storage         | Pre-storage           |
| **Purpose**      | Running the business | Routing & Validation  |
