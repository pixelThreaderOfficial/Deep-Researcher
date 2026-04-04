"""
## Description

Initializes the task scheduler module and exposes a pre-configured, global
`Scheduler` instance to be used across the application for background task
management and worker queueing.

This module now uses package-local imports (relative import) so it works
when imported as part of the `agents` package or when the package is
installed/embedded in larger applications.

## Usage Examples

Basic startup and scheduling example (recommended pattern):

```python
import asyncio
from agents.utils.task_scheduler import scheduler  # import module-level instance

async def main():
    # Ensure workers are started once during app startup
    await scheduler.start()

    # Schedule a task by passing the callable and a params dict
    # The target callable will be invoked as: func(**params)
    await scheduler.schedule(my_async_or_sync_func, params={"name": "job1", "timeout": 5})

    # Wait for all queued tasks to complete (graceful)
    await scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

If you prefer to manage your own Scheduler instance (for tests or non-global usage):

```python
from agents.utils.task_scheduler.scheduler import Scheduler
import asyncio

async def main():
    local_scheduler = Scheduler(workers=2)
    await local_scheduler.start()
    await local_scheduler.schedule(my_func, params={"x": 1})
    await local_scheduler.shutdown()

asyncio.run(main())
```

## Parameters

- None (Module level initialization)

## Returns

`None`

## Side Effects

- Instantiates a global `Scheduler` object with 4 default workers.
- Sets up the underlying `TaskQueue` ready for global application usage.

## Debug Notes

- Import the `scheduler` instance to enqueue tasks from anywhere in the backend,
  or instantiate your own `Scheduler` for isolated contexts (tests).
- `scheduler.start()` must be awaited before scheduling tasks.
- `scheduler.shutdown()` will wait for the queue to drain; it does not forcibly cancel
  in-flight tasks.

## Customization

- Modify the `workers=4` argument below to scale the default concurrent background task capacity globally.
"""

from .scheduler import Scheduler

__all__ = ["scheduler", "Scheduler"]

# Global, shared scheduler instance used by the application.
# Note: call `await scheduler.start()` during application startup before scheduling tasks.
scheduler: Scheduler = Scheduler(workers=4)
