"""Unit tests for lifecycle event publishing."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.trading.tasks.lifecycle_events import (
    CallbackLifecycleEventSink,
    CeleryTaskStatusLifecycleSink,
    ExecutionArtifactsLifecycleSink,
    TaskLifecycleEventPublisher,
    TaskLifecycleKind,
    build_lifecycle_event_spec,
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


def test_execution_artifacts_sink_only_handles_terminal_kinds() -> None:
    logger = MagicMock()
    sync_artifacts = MagicMock()
    sink = ExecutionArtifactsLifecycleSink(
        logger=logger,
        sync_artifacts=sync_artifacts,
    )
    task = MagicMock(pk="task-1", status="stopped", name="Task")

    publisher = TaskLifecycleEventPublisher(logger=logger, sinks=(sink,))

    publisher.publish(
        task=task,
        task_type="trading",
        kind="task_stop_requested",
        description="Task stop requested",
    )
    publisher.publish(
        task=task,
        task_type="trading",
        kind="task_cancelled",
        description="Task cancelled",
    )

    sync_artifacts.assert_called_once_with(task=task, task_type="trading")


def test_celery_status_sink_updates_terminal_status() -> None:
    logger = MagicMock()
    sink = CeleryTaskStatusLifecycleSink(logger=logger)
    task = MagicMock(pk="task-1", execution_id="exec-1", status="failed", name="Task")

    from apps.trading.tasks import lifecycle_events

    original = lifecycle_events.CeleryTaskStatus
    try:
        lifecycle_events.CeleryTaskStatus = MagicMock()
        lifecycle_events.CeleryTaskStatus.Status.FAILED = "failed"
        lifecycle_events.CeleryTaskStatus.Status.STOPPED = "stopped"
        lifecycle_events.CeleryTaskStatus.Status.COMPLETED = "completed"
        publisher = TaskLifecycleEventPublisher(logger=logger, sinks=(sink,))
        publisher.publish(
            task=task,
            task_type="trading",
            kind="task_failed",
            description="Trading task failed: RuntimeError: boom",
        )
        lifecycle_events.CeleryTaskStatus.objects.filter.assert_called_once_with(
            task_name="trading.tasks.run_trading_task",
            instance_key="task-1:exec-1",
        )
    finally:
        lifecycle_events.CeleryTaskStatus = original


def test_build_lifecycle_event_spec_applies_template_defaults() -> None:
    spec = build_lifecycle_event_spec(kind=TaskLifecycleKind.STOPPED)

    assert spec.kind == TaskLifecycleKind.STOPPED
    assert spec.description == "Task stopped"
    assert spec.log_message == "Task stopped"
