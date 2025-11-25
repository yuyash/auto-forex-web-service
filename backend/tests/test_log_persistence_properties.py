"""
Property-based tests for log persistence.

**Feature: websocket-to-http-polling-migration, Property 1: Log persistence completeness**

Tests that all log messages generated during task execution are stored
and retrievable from the database.

Requirements: 1.1, 6.1, 6.2, 6.3
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from rest_framework.test import APIClient

from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus, TaskType
from trading.execution_models import TaskExecution
from trading.models import StrategyConfig

User = get_user_model()


# Strategy for generating log levels
log_levels = st.sampled_from(["INFO", "WARNING", "ERROR", "DEBUG"])


# Strategy for generating log messages
log_messages = st.text(
    min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=["Cs"])
)


# Strategy for generating a single log entry
@st.composite
def log_entry(draw):
    """Generate a single log entry."""
    return {
        "timestamp": timezone.now().isoformat(),
        "level": draw(log_levels),
        "message": draw(log_messages),
    }


# Strategy for generating a list of log entries
log_entries_list = st.lists(log_entry(), min_size=1, max_size=50)


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create test strategy configuration."""
    return StrategyConfig.objects.create(
        user=user,
        name="Test Strategy",
        strategy_type="MA_CROSSOVER",
        parameters={
            "fast_period": 10,
            "slow_period": 20,
            "instrument": "EUR_USD",
            "granularity": "M5",
        },
    )


@pytest.mark.django_db
class TestLogPersistenceProperties:
    """Property-based tests for log persistence."""

    @given(logs=log_entries_list)
    @settings(
        max_examples=20,
        deadline=5000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_log_persistence_completeness(self, logs, api_client, user, strategy_config):
        """
        **Feature: websocket-to-http-polling-migration, Property 1: Log persistence completeness**

        Property: For any task execution that generates log messages,
        all log messages should be stored in the database with timestamps
        and severity levels.

        This test generates random log messages and verifies that:
        1. All logs are stored in the database
        2. All logs are retrievable via the API
        3. Log count matches what was stored
        4. Each log has timestamp, level, and message

        Requirements: 1.1, 6.1, 6.2, 6.3
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a task with unique name for each Hypothesis iteration
        unique_name = f"Property Test Backtest {uuid.uuid4().hex[:8]}"
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name=unique_name,
            description="Test log persistence",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        # Create execution with generated logs
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=50,
            started_at=timezone.now(),
            logs=logs,
        )

        # Verify logs are stored in database
        execution.refresh_from_db()
        assert len(execution.logs) == len(logs)

        # Verify all logs have required fields
        for stored_log in execution.logs:
            assert "timestamp" in stored_log
            assert "level" in stored_log
            assert "message" in stored_log
            assert stored_log["level"] in ["INFO", "WARNING", "ERROR", "DEBUG"]

        # Retrieve logs via API
        logs_url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(logs_url)

        # Verify API response
        assert response.status_code == 200
        assert response.data["count"] == len(logs)
        assert len(response.data["results"]) == len(logs)

        # Verify each log in API response has required fields
        for api_log in response.data["results"]:
            assert "timestamp" in api_log
            assert "level" in api_log
            assert "message" in api_log
            assert "execution_number" in api_log
            assert api_log["execution_number"] == 1

        # Verify log messages match (order may differ due to reverse chronological)
        stored_messages = {log["message"] for log in logs}
        retrieved_messages = {log["message"] for log in response.data["results"]}
        assert stored_messages == retrieved_messages

        # Verify log levels match
        stored_levels = {log["level"] for log in logs}
        retrieved_levels = {log["level"] for log in response.data["results"]}
        assert stored_levels == retrieved_levels

    @given(
        logs_batch1=log_entries_list,
        logs_batch2=log_entries_list,
    )
    @settings(
        max_examples=15,
        deadline=5000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_log_persistence_with_updates(
        self, logs_batch1, logs_batch2, api_client, user, strategy_config
    ):
        """
        Property: For any task execution that generates log messages in batches,
        all log messages should be stored and retrievable, including updates.

        This test verifies that logs can be added incrementally and all are persisted.

        Requirements: 1.1, 6.1, 6.2, 6.3
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a task with unique name for each Hypothesis iteration
        unique_name = f"Property Test Incremental {uuid.uuid4().hex[:8]}"
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name=unique_name,
            description="Test incremental log persistence",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        # Create execution with first batch of logs
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=25,
            started_at=timezone.now(),
            logs=logs_batch1,
        )

        # Verify first batch is stored
        execution.refresh_from_db()
        assert len(execution.logs) == len(logs_batch1)

        # Add second batch of logs
        execution.logs.extend(logs_batch2)
        execution.progress = 75
        execution.save()

        # Verify both batches are stored
        execution.refresh_from_db()
        total_logs = len(logs_batch1) + len(logs_batch2)
        assert len(execution.logs) == total_logs

        # Retrieve logs via API
        logs_url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(logs_url)

        # Verify all logs are retrievable
        assert response.status_code == 200
        assert response.data["count"] == total_logs
        assert len(response.data["results"]) == total_logs

        # Verify all messages are present
        all_stored_messages = {log["message"] for log in logs_batch1 + logs_batch2}
        retrieved_messages = {log["message"] for log in response.data["results"]}
        assert all_stored_messages == retrieved_messages

    @given(logs=log_entries_list)
    @settings(
        max_examples=15,
        deadline=5000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_log_persistence_after_completion(self, logs, api_client, user, strategy_config):
        """
        Property: For any completed task, all log messages should remain
        accessible via the logs API.

        This test verifies that logs persist after task completion.

        Requirements: 1.1, 6.1, 6.2, 6.3, 7.6
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a task with unique name for each Hypothesis iteration
        unique_name = f"Property Test Completed {uuid.uuid4().hex[:8]}"
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name=unique_name,
            description="Test log persistence after completion",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        # Create execution with logs
        execution = TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=50,
            started_at=timezone.now(),
            logs=logs,
        )

        # Complete the task
        execution.status = TaskStatus.COMPLETED
        execution.progress = 100
        execution.completed_at = timezone.now()
        execution.save()

        task.status = TaskStatus.COMPLETED
        task.save()

        # Verify logs are still accessible after completion
        logs_url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})
        response = api_client.get(logs_url)

        assert response.status_code == 200
        assert response.data["count"] == len(logs)
        assert len(response.data["results"]) == len(logs)

        # Verify all log data is intact
        for api_log in response.data["results"]:
            assert "timestamp" in api_log
            assert "level" in api_log
            assert "message" in api_log
            assert api_log["level"] in ["INFO", "WARNING", "ERROR", "DEBUG"]

    @given(
        info_logs=st.lists(
            st.builds(
                dict,
                timestamp=st.just(timezone.now().isoformat()),
                level=st.just("INFO"),
                message=log_messages,
            ),
            min_size=1,
            max_size=20,
        ),
        error_logs=st.lists(
            st.builds(
                dict,
                timestamp=st.just(timezone.now().isoformat()),
                level=st.just("ERROR"),
                message=log_messages,
            ),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(
        max_examples=15,
        deadline=5000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_log_level_filtering(self, info_logs, error_logs, api_client, user, strategy_config):
        """
        Property: For any task with logs at different levels,
        filtering by level should return only logs at that level.

        Requirements: 1.4, 6.4
        """
        # Authenticate
        api_client.force_authenticate(user=user)

        # Create a task with unique name for each Hypothesis iteration
        unique_name = f"Property Test Filtering {uuid.uuid4().hex[:8]}"
        task = BacktestTask.objects.create(
            user=user,
            config=strategy_config,
            name=unique_name,
            description="Test log level filtering",
            status=TaskStatus.RUNNING,
            instrument="EUR_USD",
            start_time=timezone.now() - timedelta(days=7),
            end_time=timezone.now() - timedelta(days=1),
        )

        # Combine logs
        all_logs = info_logs + error_logs

        # Create execution with mixed log levels
        TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
            progress=50,
            started_at=timezone.now(),
            logs=all_logs,
        )

        logs_url = reverse("trading:backtest_task_logs", kwargs={"task_id": task.pk})

        # Test filtering by INFO level
        response = api_client.get(logs_url, {"level": "INFO"})
        assert response.status_code == 200
        assert response.data["count"] == len(info_logs)
        assert all(log["level"] == "INFO" for log in response.data["results"])

        # Test filtering by ERROR level
        response = api_client.get(logs_url, {"level": "ERROR"})
        assert response.status_code == 200
        assert response.data["count"] == len(error_logs)
        assert all(log["level"] == "ERROR" for log in response.data["results"])

        # Test no filter returns all logs
        response = api_client.get(logs_url)
        assert response.status_code == 200
        assert response.data["count"] == len(all_logs)
