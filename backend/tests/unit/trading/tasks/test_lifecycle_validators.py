"""Unit tests for lifecycle command validators."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus
from apps.trading.services.resume_config import ResumeConfigurationError
from apps.trading.tasks.lifecycle_validators import ResumeCommandValidator
from apps.trading.tasks.service import TaskValidationError


def _make_validator() -> tuple[ResumeCommandValidator, MagicMock, MagicMock]:
    logger = MagicMock()
    risk_guard = MagicMock()
    return (
        ResumeCommandValidator(
            logger=logger,
            ensure_dispatch_risk_guard_allows=risk_guard,
        ),
        logger,
        risk_guard,
    )


def test_resume_validator_rejects_invalid_status() -> None:
    task = MagicMock(pk=uuid4(), status=TaskStatus.RUNNING, execution_id=uuid4())
    validator, _, risk_guard = _make_validator()

    with pytest.raises(TaskValidationError, match="cannot be resumed from"):
        validator.validate(task=task, task_type="backtest")

    risk_guard.assert_not_called()


def test_resume_validator_requires_execution_id() -> None:
    task = MagicMock(pk=uuid4(), status=TaskStatus.PAUSED, execution_id=None)
    validator, _, risk_guard = _make_validator()

    with pytest.raises(TaskValidationError, match="execution_id"):
        validator.validate(task=task, task_type="backtest")

    risk_guard.assert_not_called()


def test_resume_validator_maps_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    task = MagicMock(pk=uuid4(), status=TaskStatus.PAUSED, execution_id=uuid4())
    validator, _, risk_guard = _make_validator()
    error = ResumeConfigurationError(
        "blocked config",
        code="resume_blocked",
        blocked_fields=["strategy_type"],
    )

    def raise_config_error(**_kwargs):
        raise error

    monkeypatch.setattr(
        "apps.trading.services.resume_config.validate_resume_configuration",
        raise_config_error,
    )

    with pytest.raises(TaskValidationError, match="blocked config") as exc_info:
        validator.validate(task=task, task_type="backtest")

    assert exc_info.value.resume_config_error == error.as_payload()
    risk_guard.assert_not_called()


def test_resume_validator_logs_config_and_checks_risk_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = MagicMock(pk=uuid4(), status=TaskStatus.PAUSED, execution_id=uuid4())
    audit = MagicMock()
    validator, logger, risk_guard = _make_validator()
    validate_config = MagicMock(return_value=audit)
    log_config = MagicMock()
    monkeypatch.setattr(
        "apps.trading.services.resume_config.validate_resume_configuration",
        validate_config,
    )
    monkeypatch.setattr(
        "apps.trading.services.resume_config.log_effective_resume_configuration",
        log_config,
    )

    validator.validate(task=task, task_type="backtest")

    validate_config.assert_called_once_with(task=task, task_type="backtest")
    log_config.assert_called_once_with(logger=logger, audit=audit, task=task)
    risk_guard.assert_called_once_with(task)
