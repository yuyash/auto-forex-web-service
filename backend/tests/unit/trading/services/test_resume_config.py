"""Tests for resume configuration validation and audit helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus
from apps.trading.models import TaskExecutionSnapshot
from apps.trading.services.execution_snapshots import _snapshot_task_config
from apps.trading.services.resume_config import (
    build_config_snapshot_defaults,
    validate_resume_configuration,
)
from tests.integration.factories import BacktestTaskFactory


@pytest.mark.django_db
def test_resume_allows_parameter_increase_and_reports_changes() -> None:
    task = BacktestTaskFactory(status=TaskStatus.STOPPED, execution_id=uuid4())
    task.refresh_from_db()
    TaskExecutionSnapshot.objects.create(
        task_type="backtest",
        task_id=task.pk,
        execution_id=task.execution_id,
        task_config=_snapshot_task_config(task),
        strategy_config={
            "id": str(task.config.pk),
            "name": task.config.name,
            "strategy_type": "snowball",
            "parameters": {"base_units": 1000, "r_max": 5},
        },
    )
    task.config.parameters = {"base_units": 2000, "r_max": 6}
    task.config.save(update_fields=["parameters"])
    task.refresh_from_db()

    audit = validate_resume_configuration(task=task, task_type="backtest")

    assert audit.parameter_changes["base_units"] == {"previous": 1000, "current": 2000}
    assert audit.parameter_changes["r_max"] == {"previous": 5, "current": 6}
    assert audit.effective_parameters["base_units"] == 2000


@pytest.mark.django_db
def test_resume_blocks_snowball_r_max_decrease() -> None:
    task = BacktestTaskFactory(status=TaskStatus.STOPPED, execution_id=uuid4())
    task.refresh_from_db()
    TaskExecutionSnapshot.objects.create(
        task_type="backtest",
        task_id=task.pk,
        execution_id=task.execution_id,
        task_config=_snapshot_task_config(task),
        strategy_config={
            "id": str(task.config.pk),
            "name": task.config.name,
            "strategy_type": "snowball",
            "parameters": {"base_units": 1000, "r_max": 5},
        },
    )
    task.config.parameters = {"base_units": 1000, "r_max": 4}
    task.config.save(update_fields=["parameters"])
    task.refresh_from_db()

    with pytest.raises(ValueError, match="decreasing r_max"):
        validate_resume_configuration(task=task, task_type="backtest")


@pytest.mark.django_db
def test_resume_compares_against_latest_snapshot_current_config() -> None:
    task = BacktestTaskFactory(status=TaskStatus.STOPPED, execution_id=uuid4())
    task.refresh_from_db()
    TaskExecutionSnapshot.objects.create(
        task_type="backtest",
        task_id=task.pk,
        execution_id=task.execution_id,
        task_config=_snapshot_task_config(task),
        strategy_config={
            "id": str(task.config.pk),
            "name": task.config.name,
            "strategy_type": "snowball",
            "parameters": {"base_units": 1000, "r_max": 5},
            "initial": {
                "id": str(task.config.pk),
                "name": task.config.name,
                "strategy_type": "snowball",
                "parameters": {"base_units": 1000, "r_max": 5},
            },
            "current": {
                "id": str(task.config.pk),
                "name": task.config.name,
                "strategy_type": "snowball",
                "parameters": {"base_units": 1000, "r_max": 6},
            },
            "revisions": [],
        },
    )
    task.config.parameters = {"base_units": 1000, "r_max": 5}
    task.config.save(update_fields=["parameters"])
    task.refresh_from_db()

    with pytest.raises(ValueError, match="decreasing r_max"):
        validate_resume_configuration(task=task, task_type="backtest")


@pytest.mark.django_db
def test_snapshot_defaults_preserve_initial_config_and_append_revision() -> None:
    task = BacktestTaskFactory(status=TaskStatus.STOPPED, execution_id=uuid4())
    task.refresh_from_db()
    snapshot = TaskExecutionSnapshot.objects.create(
        task_type="backtest",
        task_id=task.pk,
        execution_id=task.execution_id,
        task_config=_snapshot_task_config(task),
        strategy_config={
            "id": str(task.config.pk),
            "name": "Original",
            "strategy_type": "snowball",
            "parameters": {"base_units": 1000, "r_max": 5},
        },
    )
    task.config.name = "Edited"
    task.config.parameters = {"base_units": 2000, "r_max": 6}
    task.config.save(update_fields=["name", "parameters"])
    task.refresh_from_db()

    defaults = build_config_snapshot_defaults(snapshot=snapshot, task=task)

    strategy_config = defaults["strategy_config"]
    assert strategy_config["initial"]["name"] == "Original"
    assert strategy_config["current"]["name"] == "Edited"
    assert strategy_config["current"]["configuration_revision"] == task.config.revision
    assert strategy_config["current"]["configuration_hash"] == task.config.config_hash
    assert strategy_config["current"]["parameters"]["base_units"] == 2000
    assert strategy_config["revisions"]
