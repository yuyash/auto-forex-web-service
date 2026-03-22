"""Unit tests for lifecycle event publishing."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.trading.tasks.lifecycle_events import (
    CallbackLifecycleEventSink,
    TaskLifecycleEventPublisher,
)


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


def test_callback_sink_forwards_event() -> None:
    callback = MagicMock()
    sink = CallbackLifecycleEventSink(callback=callback)
    logger = MagicMock()
    task = MagicMock(pk="task-1", status="running", name="Task")

    publisher = TaskLifecycleEventPublisher(logger=logger, sinks=(sink,))

    publisher.publish(
        task=task,
        task_type="trading",
        kind="task_paused",
        description="Task paused",
    )

    callback.assert_called_once()
    assert callback.call_args.args[0].kind == "task_paused"
