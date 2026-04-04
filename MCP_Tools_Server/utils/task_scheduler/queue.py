"""
## Description

Defines the core data structures for the background task scheduling system.
Includes the `Task` dataclass for representing individual units of work
and the `TaskQueue` class, which provides an asynchronous wrapper around
`asyncio.Queue` for managing task distribution.

## Parameters

- None (Module level)

## Returns

`None`

## Raises

- None

## Side Effects

- None

## Debug Notes

- Used heavily by both `Scheduler` and `Worker` classes for inter-task communication.

## Customization

- N/A
"""

import asyncio
from dataclasses import dataclass
from typing import Callable


@dataclass
class Task:
    """
    ## Description

    A data class representing a single background task to be executed by a worker.
    It encapsulates the function and its parameters as a single dict for consistency.

    ## Parameters

    - `func` (`Callable`)
      - Description: The target function or coroutine to be executed.
      - Constraints: Can be synchronous or asynchronous.
      - Example: `my_async_function`

    - `params` (`dict`)
      - Description: Keyword arguments to pass to the function.
      - Constraints: Must match the function signature.
      - Example: `{"name": "test", "timeout": 10}`

    - `retries` (`int`, optional)
      - Description: Current number of execution attempts.
      - Constraints: Must be >= 0. Default is 0.
      - Example: `1`

    - `max_retries` (`int`, optional)
      - Description: Maximum allowed execution attempts before permanent failure.
      - Constraints: Must be >= 0. Default is 3.
      - Example: `5`
    """

    func: Callable
    params: dict
    retries: int = 0
    max_retries: int = 3


class TaskQueue:
    """
    ## Description

    An asynchronous wrapper around `asyncio.Queue` designed specifically to
    manage `Task` objects for background execution. Provides a simplified
    interface for task enqueuing and dequeuing.
    """

    def __init__(self):
        """
        ## Description

        Initializes the TaskQueue by creating an underlying unbounded asyncio Queue.

        ## Parameters

        - None

        ## Returns

        `None`

        ## Raises

        - None

        ## Side Effects

        - Instantiates `asyncio.Queue`.

        ## Debug Notes

        - Ensure this is called within a running event loop if strict asyncio
          event loop attachment is required by the Python version.

        ## Customization

        - Add a `maxsize` parameter to `asyncio.Queue` if you need backpressure.
        """
        self.queue = asyncio.Queue()

    async def put(self, task: Task):
        """
        ## Description

        Asynchronously adds a new task to the internal queue.

        ## Parameters

        - `task` (`Task`)
          - Description: The task definition to be enqueued.
          - Constraints: Must be an instance of the `Task` dataclass.

        ## Returns

        `None`

        ## Raises

        - None

        ## Side Effects

        - Increases the size of the internal queue.
        - Wakes up any waiting consumers (workers).

        ## Debug Notes

        - If the queue was initialized with `maxsize`, this could block until space is available.

        ## Customization

        - Add logging here to track enqueue rates.
        """
        await self.queue.put(task)

    async def get(self) -> Task:
        """
        ## Description

        Asynchronously dequeues the next available task from the queue.
        Blocks if the queue is currently empty until a task is available.

        ## Parameters

        - None

        ## Returns

        `Task`

        Structure:
        ```python
        Task(
            func=my_func,
            args=(1,),
            kwargs={"a": 2},
            retries=0,
            max_retries=3
        )
        ```

        ## Raises

        - None

        ## Side Effects

        - Decreases the size of the internal queue.

        ## Debug Notes

        - A worker calling this will pause execution until a task is pushed via `put`.

        ## Customization

        - N/A
        """
        return await self.queue.get()

    def task_done(self):
        """
        ## Description

        Signals to the internal queue that a previously dequeued task has been
        fully processed. This is essential for `join()` to function correctly.

        ## Parameters

        - None

        ## Returns

        `None`

        ## Raises

        - `ValueError`
          - If called more times than there are items placed in the queue.

        ## Side Effects

        - Decrements the internal unfinished tasks counter.

        ## Debug Notes

        - MUST be called exactly once per task fetched via `get()`, usually in a `finally` block.

        ## Customization

        - N/A
        """
        self.queue.task_done()

    async def join(self):
        """
        ## Description

        Blocks the calling coroutine until all items in the queue have been
        retrieved and processed (i.e., `task_done()` has been called for every item).

        ## Parameters

        - None

        ## Returns

        `None`

        ## Raises

        - None

        ## Side Effects

        - Pauses execution flow until queue processing is fully resolved.

        ## Debug Notes

        - Used heavily during shutdown sequences to ensure no tasks are dropped.

        ## Customization

        - Wrap with `asyncio.wait_for` to implement a forced shutdown timeout.
        """
        await self.queue.join()
