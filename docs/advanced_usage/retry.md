# Retry Strategies

Jobify provides a powerful retry mechanism based on exponential backoff and jitter, allowing you to handle transient failures gracefully while avoiding "thundering herd" problems.

<div class="grid cards" markdown>

- :material-chart-bell-curve:{ .lg .middle } **Exponential Backoff**

    ***

    Automatically increases the delay between retries to give downstream systems time to recover.

- :material-shuffle-variant:{ .lg .middle } **Jitter Strategy**

    ***

    Randomizes retry delays to prevent multiple failed jobs from retrying at the exact same millisecond.

- :material-filter-outline:{ .lg .middle } **Exception Filtering**

    ***

    Target specific exceptions for retries while letting fatal errors fail immediately via exclusion lists.

- :material-sync-alert:{ .lg .middle } **Airflow Alignment**

    ***

    Predictable `retries` parameter matching industry standards for intuitive configuration.

</div>

## Basic Usage

For simple scenarios, you can pass an integer to the `retry` parameter of the `@app.task` decorator. This specifies the number of retries to perform after the initial failure.

```python
@app.task(retry=3)
def my_task():
    # Will be tried 4 times total: 1 original + 3 retries
    ...
```

By default, an integer `retry=N` is converted to a `SmartRetry` object with default backoff settings.

## Advanced Usage: `SmartRetry`

For more control, use the `SmartRetry` object.

```python
from jobify import Jobify, SmartRetry

app = Jobify()

@app.task(
    retry=SmartRetry(
        retries=5,
        initial_delay=1.0,
        max_delay=300.0,
        backoff_factor=2.0,
        jitter=True,
        include_exceptions=(IOError, ConnectionError),
        exclude_exceptions=(ValueError,)
    )
)
def sensitive_task():
    ...
```

### Configuration Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `retries` | `int` | **Required** | Number of retries after the first failure. |
| `initial_delay` | `float` | `0.5` | Delay in seconds for the first retry. |
| `max_delay` | `float` | `60.0` | Maximum possible delay between retries. |
| `backoff_factor` | `float` | `2.0` | Base for exponential growth (`initial * factor^attempt`). |
| `jitter` | `bool` | `True` | Whether to apply "Equal Jitter" to the delay. |
| `include_exceptions` | `tuple` | `(Exception,)` | Exceptions that trigger a retry. |
| `exclude_exceptions` | `tuple` | `()` | Exceptions that abort retries immediately. |

## Backoff Logic

The delay for each attempt is calculated as:
`min(initial_delay * backoff_factor ** (attempt - 1), max_delay)`

If `jitter=True`, the delay is randomized in the range `[delay/2, delay]`.

## Aborting Retries

To stop retrying immediately when a specific fatal error occurs, use the `exclude_exceptions` attribute. This is the replacement for the deprecated `NoResultError`.

```python
class FatalError(Exception): ...

@app.task(
    retry=SmartRetry(retries=3, exclude_exceptions=(FatalError,))
)
def my_task():
    if not database_connected():
        raise FatalError("Cannot proceed") # No retries will be attempted
```
