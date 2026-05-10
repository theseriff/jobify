# System Time & Scheduling

Jobify is designed for performance and precision by completely avoiding **polling**. This architectural choice provides significant advantages but requires an understanding of how Jobify interacts with the system clock.

<div class="grid cards" markdown>

- :material-meter-electric:{ .lg .middle } **Zero Idle CPU**

    ***

    No background loops checking for tasks. Resources are consumed only during execution.

- :material-target:{ .lg .middle } **High Precision**

    ***

    Triggered by low-level OS event notification mechanisms (epoll, kqueue).

- :material-chart-bell-curve-cumulative:{ .lg .middle } **High Scalability**

    ***

    Efficiently handles thousands of concurrent timers via the `asyncio` event loop.

- :material-lightning-bolt-outline:{ .lg .middle } **Native Performance**

    ***

    Directly leverages the speed and efficiency of the underlying OS event loop.

</div>

## Polling vs. Native Timers

Most Python schedulers (like APScheduler v3 or Celery) rely on a **polling loop** that repeatedly checks the current time against a task list.

**Jobify uses `asyncio.loop.call_at`.** When you schedule a task, Jobify calculates the exact moment it should run and registers a timer directly in the event loop.

## The Trade-off: Clock Adjustments

Because Jobify registers a specific delay once, it is sensitive to **significant system clock shifts** (manual changes or NTP jumps).

### Wall-Clock vs. Monotonic Time

| Type | Name | Behavior |
| :--- | :--- | :--- |
| :material-clock-outline: | **Wall-Clock** (`datetime.now()`) | Current calendar time. Can jump forward/backward. |
| :material-clock-fast: | **Monotonic** (`time.monotonic()`) | Steadily increasing. Unaffected by system time changes. |

### Internal Flow

1.  **Read Wall-Clock**: Get current time (e.g., 14:50).
2.  **Calculate Delay**: Scheduled for 15:00 → 10 minute (600s) delay.
3.  **Register Timer**: Tell the event loop: *"Run this in 600s of Monotonic time"*.

!!! warning "Clock Shift Impact"
    If the system clock is manually changed to 15:00 immediately after scheduling, the **Monotonic clock does not change**. The task will still run after 600s of real time (when the system clock shows 15:10).

## Handling Time Changes

If your system clock changes significantly (e.g., after a long sleep or NTP correction), simply **restart the application**.

On startup, Jobify will:

1.  Read the **updated** wall-clock time.
2.  Recalculate delays for all stored tasks.
3.  Register **fresh timers** with the event loop.

This ensures all tasks align correctly with the new system time.
