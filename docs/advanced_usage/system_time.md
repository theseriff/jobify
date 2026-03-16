# System Time and Scheduling Trade-offs

One of the key architectural decisions in Jobify is to completely avoid
**polling**. While this approach provides significant advantages in
terms of performance and precision, it also introduces a specific
behavior when the operating system's clock is adjusted.

## Polling vs. Native Timers

Most Python scheduling frameworks, such as APScheduler v3 and Celery,
rely on a **polling loop**. Typically, this involves a continuous
process like:

```python
while True:
    sleep(1)
    check_scheduled_tasks()
```

In this model, the scheduler repeatedly checks the current system time
against a list of scheduled jobs.

**Jobify takes a different approach.** Instead of polling, it uses the
`asyncio.loop.call_at` API. When a task is scheduled, Jobify calculates
the exact moment the task should run and registers a timer directly in
the event loop.

This allows the operating system's event notification mechanisms (such
as epoll or kqueue) to wake the scheduler precisely when the task is
due.

## Benefits of Jobify's Approach

This design provides several important advantages:

- **Zero Idle CPU Usage**:

    > The scheduler does not run periodic checks.</br>
    > CPU resources are used only when a scheduled task actually needs to execute.

- **High Precision**:

    > Tasks are triggered directly by the event loop's timer system,</br>
    > eliminating the timing jitter introduced by polling intervals.

- **High Scalability**:

    > The asyncio event loop efficiently manages large numbers of timers,</br>
    > allowing Jobify to handle thousands of scheduled tasks with minimal overhead.

## The Trade-off: System Time Adjustments

The trade-off for this efficiency is how Jobify behaves when the
**system clock (wall-clock time)** changes after a task has already been
scheduled.

### Wall Clock vs Monotonic Time

Two different time concepts are involved:

#### Wall-clock time (`datetime.now()`)

Represents the system's current calendar time. This value may change due
to:

- manual system time adjustments
- NTP synchronization
- daylight saving time transitions

#### Monotonic time (`time.monotonic()`)

A steadily increasing clock that is **not affected by system time
changes**.\
`asyncio` relies on a monotonic clock for its internal timing.

### What Happens Internally

Suppose a task is scheduled to run at **15:00**, and the current time is
**14:50**.

Jobify performs the following steps:

1.  Reads the current **wall-clock time** (14:50).

2.  Computes the delay until the scheduled time (10 minutes / 600
    seconds).

3.  Registers a timer with the event loop:

    > Execute this task 600 seconds from now.

From this point forward, the timer is based entirely on **monotonic
time**.

If the system clock is manually changed to **15:00** immediately after
scheduling, the monotonic clock does **not** change. The event loop will
still wait for the full 600 seconds before executing the task.

As a result, the task would run when the system clock shows **15:10**.

## Why This Design Was Chosen

This behavior is an **intentional design trade-off**.

By relying on native event loop timers instead of polling, Jobify gains:

- lower CPU overhead
- higher scheduling precision
- better scalability for large numbers of tasks

The downside is that timers already registered in the event loop do not
automatically adjust when the system clock changes.

## Handling Time Changes

If the system time changes significantly while Jobify is running, simply
**restart the application**.

Upon startup, Jobify will:

1.  Read the current wall-clock time
2.  Recalculate delays for all scheduled tasks
3.  Register fresh timers with the event loop

This ensures that all tasks are scheduled correctly according to the
updated system time.
