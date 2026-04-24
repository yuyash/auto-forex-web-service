from types import SimpleNamespace

from apps.trading.services import summary


def test_compute_stop_reason_ignores_progress_only_heartbeat(monkeypatch) -> None:
    monkeypatch.setattr(
        summary,
        "_fetch_celery_status_message",
        lambda **_: "Processed 90528 ticks",
    )

    stop_reason = summary._compute_stop_reason(
        task_type="backtest",
        task_id="task-1",
        execution_id="execution-1",
        task=SimpleNamespace(status="completed", execution_id="execution-1"),
    )

    assert stop_reason == "Execution completed successfully"


def test_compute_stop_reason_keeps_actionable_status_message(monkeypatch) -> None:
    monkeypatch.setattr(
        summary,
        "_fetch_celery_status_message",
        lambda **_: "Execution stopped by external signal",
    )

    stop_reason = summary._compute_stop_reason(
        task_type="backtest",
        task_id="task-1",
        execution_id="execution-1",
        task=SimpleNamespace(status="stopped", execution_id="execution-1"),
    )

    assert stop_reason == "Execution stopped by external signal"
