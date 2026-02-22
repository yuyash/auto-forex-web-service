"""Control-related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskControl:
    """Control flags for task execution lifecycle.

    This dataclass provides flags that control the execution flow of a task.
    These flags are checked periodically during execution to handle stop requests.

    Attributes:
        should_stop: Flag indicating the task should stop"""

    should_stop: bool = False
