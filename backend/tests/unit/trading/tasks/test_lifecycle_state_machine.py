from apps.trading.enums import TaskStatus
from apps.trading.tasks.lifecycle_state_machine import allowed_statuses_for_command


def test_allowed_statuses_for_resume_backtest() -> None:
    allowed = allowed_statuses_for_command("resume_backtest")
    assert TaskStatus.PAUSED in allowed
    assert TaskStatus.STOPPED in allowed


def test_unknown_command_returns_empty_tuple() -> None:
    assert allowed_statuses_for_command("unknown") == ()
