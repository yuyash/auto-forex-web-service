"""Integration tests for recovery attempt API."""

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.trading.enums import TaskType
from apps.trading.models import RecoveryAttempt
from tests.integration.factories import UserFactory


def _auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestRecoveryAttemptsAPI:
    """Tests for read-only recovery attempt listing."""

    def test_requires_authentication(self):
        response = APIClient().get("/api/trading/recovery-attempts/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error_code"] == "not_authenticated"

    def test_lists_recovery_attempts(self):
        task_id = uuid4()
        attempt = RecoveryAttempt.objects.create(
            task_type=TaskType.TRADING,
            task_id=task_id,
            execution_id=uuid4(),
            source="celery_beat",
            action="resume_same_execution",
            result="success",
            reason="orphaned_trading",
            metadata={"status": "running"},
        )

        response = _auth_client(UserFactory()).get("/api/trading/recovery-attempts/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        result = response.data["results"][0]
        assert result["id"] == str(attempt.id)
        assert result["task_id"] == str(task_id)
        assert result["result"] == "success"

    def test_filters_recovery_attempts(self):
        matching_task_id = uuid4()
        RecoveryAttempt.objects.create(
            task_type=TaskType.TRADING,
            task_id=matching_task_id,
            source="celery_beat",
            action="resume_same_execution",
            result="success",
        )
        RecoveryAttempt.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=uuid4(),
            source="worker_ready",
            action="mark_stopped",
            result="skipped",
        )

        response = _auth_client(UserFactory()).get(
            "/api/trading/recovery-attempts/",
            {
                "task_type": TaskType.TRADING,
                "task_id": str(matching_task_id),
                "source": "celery_beat",
                "result": "success",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["task_type"] == TaskType.TRADING
