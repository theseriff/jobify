# Queue Middleware

`QueueMiddleware` gives execution control under load: bounded buffering, controlled concurrency, and optional priority routing.

<div class="grid cards" markdown>

- :material-meter-electric:{ .lg .middle } **Backpressure**

    ***

    Bounded `maxsize` prevents unbounded in-memory job growth.

- :material-tune:{ .lg .middle } **Throughput Control**

    ***

    `workers` sets max concurrent executions for safer downstream load.

- :material-sort:{ .lg .middle } **Priority Routing**

    ***

    `PriorityQueue` + `metadata.priority` runs critical jobs first.

- :material-wrench-outline:{ .lg .middle } **Tuning**

    ***

    Dynamic parameter adjustment for workers and buffer sizes.

</div>

## When to Enable

Use it when:

- jobs come in bursts
- DB/API concurrency is limited
- some jobs are business-critical and must run earlier

## Setup

=== "Default (`PriorityQueue`)"

    ```python
    import asyncio

    from jobify import Jobify
    from jobify.middleware import QueueMiddleware

    app = Jobify()
    app.add_middleware(
        QueueMiddleware(queue=asyncio.PriorityQueue(maxsize=1024), workers=10)
    )

    @app.task(metadata={"priority": 100})
    async def critical_job() -> None:
        ...

    @app.task(metadata={"priority": 10})
    async def regular_job() -> None:
        ...
    ```

    Higher `metadata.priority` runs earlier.

    Default queue: `asyncio.PriorityQueue(maxsize=1024)`.

=== "FIFO (`asyncio.Queue`)"

    ```python
    import asyncio

    from jobify import Jobify
    from jobify.middleware import QueueMiddleware

    app = Jobify()
    app.add_middleware(
        QueueMiddleware(queue=asyncio.Queue(maxsize=200), workers=20)
    )
    ```

    This is the explicit FIFO queue mode.

=== "LIFO (`asyncio.LifoQueue`)"

    ```python
    import asyncio

    from jobify import Jobify
    from jobify.middleware import QueueMiddleware

    app = Jobify()
    app.add_middleware(
        QueueMiddleware(queue=asyncio.LifoQueue(maxsize=200), workers=30)
    )
    ```

    Last in, first out: newest jobs are executed first.
    Useful for bursty/non-critical work where newer events are usually more relevant than older ones.

## Priority Examples

### 1) Critical first, regular later

```python
import asyncio

from jobify import Jobify
from jobify.middleware import QueueMiddleware

app = Jobify()
app.add_middleware(QueueMiddleware(queue=asyncio.PriorityQueue(maxsize=256), workers=1))


@app.task(metadata={"priority": 100})
async def charge_payment(order_id: str) -> str:
    return f"charged:{order_id}"


@app.task(metadata={"priority": 10})
async def send_analytics(event_id: str) -> str:
    return f"tracked:{event_id}"


async def main() -> None:
    async with app:
        low = await send_analytics.push("evt-1")
        high = await charge_payment.push("ord-1")
        await asyncio.gather(low.wait(), high.wait())
```

Even if `low` was enqueued first, `charge_payment` is executed earlier because its `priority` is higher.

### 2) Multiple levels (example policy)

```python
PRIORITY_CRITICAL = 100
PRIORITY_USER_FLOW = 50
PRIORITY_BACKGROUND = 5

@app.task(metadata={"priority": PRIORITY_CRITICAL})
async def webhook_retry() -> None: ...

@app.task(metadata={"priority": PRIORITY_USER_FLOW})
async def user_notification() -> None: ...

@app.task(metadata={"priority": PRIORITY_BACKGROUND})
async def metrics_rollup() -> None: ...
```

Use numeric bands to keep priority rules explicit and consistent across the codebase.

!!! note "Equal priority"
    Jobs with the same `metadata.priority` are not guaranteed to execute in strict FIFO order inside a `PriorityQueue`.
    If strict order matters, use `asyncio.Queue` or assign distinct priority values.

## Backpressure Behavior

!!! info "What happens when queue is full"
    Producers wait on enqueue. This slows intake and keeps execution bounded instead of growing memory usage without limit.

## Queue Choice

- `asyncio.Queue`: FIFO, most predictable default for stable pipelines.
- `asyncio.PriorityQueue`: prioritize critical work.
- `asyncio.LifoQueue`: niche LIFO workloads.

## Tuning Cheatsheet

| Parameter       | What it controls                    | Practical start                       |
| --------------- | ----------------------------------- | ------------------------------------- |
| `workers`       | concurrent executions               | set to safe downstream concurrency    |
| `queue.maxsize` | buffered jobs before producer waits | keep finite (for example, `100-1000`) |

??? warning "Common mistakes"

    - Unbounded queue sizes.
    - `workers` higher than downstream service capacity.
    - Priority values without clear business rules.
