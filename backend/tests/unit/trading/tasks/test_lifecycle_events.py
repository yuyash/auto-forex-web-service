"""Unit tests for lifecycle event publishing."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.trading.tasks.lifecycle_events import TaskLifecycleEventPublisher


def test_publisher_dispatches_to_all_sinks() -> None:
    logger = MagicMock()
    sink_one = MagicMock()
    sink_two = MagicMock()
    task = MagicMock(pk="task-1", status="running", name="Task")

    publisher = TaskLifecycleEventPublisher(
        logger=logger,
        sinks=(sink_one, sink_two),
    )

    publisher.publish(
        task=task,
        task_type="trading",
        kind="task_start_requested",
        description="Task start requested",
        extra_details={"mode": "graceful"},
    )

    sink_one.publish.assert_called_once()
    sink_two.publish.assert_called_once()
    published_event = sink_one.publish.call_args.args[0]
    assert published_event.task is task
    assert published_event.task_type == "trading"
    assert published_event.details["mode"] == "graceful"
