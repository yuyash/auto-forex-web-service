"""
Unit tests for Athena import progress tracking.

Requirements: 2.1, 2.2
"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

if TYPE_CHECKING:
    from accounts.models import User as UserType
else:
    UserType = get_user_model()

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def regular_user(db) -> "UserType":
    """Create a regular user for testing."""
    return User.objects.create_user(
        email="user@example.com",
        username="regularuser",
        password="TestPass123!",
        is_staff=False,
    )


@pytest.fixture
def admin_user(db) -> "UserType":
    """Create an admin user for testing."""
    return User.objects.create_user(
        email="admin@example.com",
        username="adminuser",
        password="AdminPass123!",
        is_staff=True,
    )


@pytest.fixture
def sample_progress_data() -> dict:
    """Create sample progress data for testing."""
    return {
        "in_progress": True,
        "current_day": 3,
        "total_days": 7,
        "percentage": 42.86,
        "status": "running",
        "message": "Importing day 3 of 7",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-07T00:00:00Z",
        "started_at": "2024-01-08T10:30:00Z",
        "completed_at": None,
        "error": None,
    }


@pytest.mark.django_db
class TestAdminAthenaImportProgressView:
    """Test suite for Athena import progress endpoint."""

    def test_admin_can_retrieve_progress(
        self, api_client: APIClient, admin_user: "UserType", sample_progress_data: dict
    ) -> None:
        """
        Test admin can retrieve import progress when import is in progress.

        Requirements: 2.1, 2.2
        """
        # Set up progress in cache
        cache.set("athena_import_progress", sample_progress_data, timeout=3600)

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_athena_import_progress")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["in_progress"] is True
        assert response.data["current_day"] == 3
        assert response.data["total_days"] == 7
        assert response.data["percentage"] == 42.86
        assert response.data["status"] == "running"
        assert response.data["message"] == "Importing day 3 of 7"
        assert response.data["start_date"] == "2024-01-01T00:00:00Z"
        assert response.data["end_date"] == "2024-01-07T00:00:00Z"
        assert response.data["started_at"] == "2024-01-08T10:30:00Z"
        assert response.data["completed_at"] is None
        assert response.data["error"] is None

        # Clean up
        cache.delete("athena_import_progress")

    def test_returns_404_when_no_import_in_progress(
        self, api_client: APIClient, admin_user: "UserType"
    ) -> None:
        """
        Test endpoint returns 404 when no import is in progress.

        Requirements: 2.1, 2.2
        """
        # Ensure no progress in cache
        cache.delete("athena_import_progress")

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_athena_import_progress")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.data
        assert "No import in progress" in response.data["error"]

    def test_regular_user_cannot_access_progress(
        self, api_client: APIClient, regular_user: "UserType", sample_progress_data: dict
    ) -> None:
        """
        Test regular user cannot access import progress.

        Requirements: 2.1, 2.2
        """
        # Set up progress in cache
        cache.set("athena_import_progress", sample_progress_data, timeout=3600)

        api_client.force_authenticate(user=regular_user)
        url = reverse("accounts:admin_athena_import_progress")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Clean up
        cache.delete("athena_import_progress")

    def test_unauthenticated_user_cannot_access_progress(
        self, api_client: APIClient, sample_progress_data: dict
    ) -> None:
        """
        Test unauthenticated user cannot access import progress.

        Requirements: 2.1, 2.2
        """
        # Set up progress in cache
        cache.set("athena_import_progress", sample_progress_data, timeout=3600)

        url = reverse("accounts:admin_athena_import_progress")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Clean up
        cache.delete("athena_import_progress")

    def test_completed_import_progress(self, api_client: APIClient, admin_user: "UserType") -> None:
        """
        Test retrieving progress for completed import.

        Requirements: 2.1, 2.2
        """
        completed_progress = {
            "in_progress": False,
            "current_day": 7,
            "total_days": 7,
            "percentage": 100.0,
            "status": "completed",
            "message": "Import completed successfully",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-07T00:00:00Z",
            "started_at": "2024-01-08T10:30:00Z",
            "completed_at": "2024-01-08T11:45:00Z",
            "error": None,
        }

        cache.set("athena_import_progress", completed_progress, timeout=3600)

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_athena_import_progress")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["in_progress"] is False
        assert response.data["status"] == "completed"
        assert response.data["percentage"] == 100.0
        assert response.data["completed_at"] == "2024-01-08T11:45:00Z"

        # Clean up
        cache.delete("athena_import_progress")

    def test_failed_import_progress(self, api_client: APIClient, admin_user: "UserType") -> None:
        """
        Test retrieving progress for failed import.

        Requirements: 2.1, 2.2
        """
        failed_progress = {
            "in_progress": False,
            "current_day": 3,
            "total_days": 7,
            "percentage": 42.86,
            "status": "failed",
            "message": "Import failed",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-07T00:00:00Z",
            "started_at": "2024-01-08T10:30:00Z",
            "completed_at": "2024-01-08T10:45:00Z",
            "error": "Connection timeout to Athena service",
        }

        cache.set("athena_import_progress", failed_progress, timeout=3600)

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_athena_import_progress")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["in_progress"] is False
        assert response.data["status"] == "failed"
        assert response.data["error"] == "Connection timeout to Athena service"

        # Clean up
        cache.delete("athena_import_progress")

    def test_cache_unavailable_returns_503(
        self, api_client: APIClient, admin_user: "UserType", monkeypatch
    ) -> None:
        """
        Test endpoint returns 503 when cache is unavailable.

        Requirements: 2.1, 2.2
        """
        from unittest.mock import patch

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_athena_import_progress")

        # Mock cache.get to raise an exception only for athena_import_progress key
        # but allow other cache operations (like rate limiting) to work normally
        original_cache_get = cache.get

        def selective_cache_get(key, *args, **kwargs):
            if key == "athena_import_progress":
                raise Exception("Cache connection failed")
            return original_cache_get(key, *args, **kwargs)

        with patch.object(cache, "get", side_effect=selective_cache_get):
            response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "error" in response.data
        assert "Progress tracking temporarily unavailable" in response.data["error"]
        assert "details" in response.data


@pytest.mark.django_db
class TestAdminTriggerAthenaImportView:
    """Test suite for concurrent import prevention in trigger endpoint."""

    def test_concurrent_import_prevention(
        self, api_client: APIClient, admin_user: "UserType"
    ) -> None:
        """
        Test that triggering import while one is in progress returns 409.

        Requirements: 1.5
        """
        # Set up an import in progress
        in_progress_data = {
            "in_progress": True,
            "current_day": 2,
            "total_days": 5,
            "percentage": 40.0,
            "status": "running",
            "message": "Importing day 2 of 5",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-05T00:00:00Z",
            "started_at": "2024-01-06T10:00:00Z",
            "completed_at": None,
            "error": None,
        }
        cache.set("athena_import_progress", in_progress_data, timeout=3600)

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_trigger_athena_import")

        # Try to trigger another import
        response = api_client.post(
            url,
            {
                "start_date": "2024-01-10T00:00:00Z",
                "end_date": "2024-01-12T00:00:00Z",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["success"] is False
        assert "Import already in progress" in response.data["error"]
        assert "already running" in response.data["message"]

        # Clean up
        cache.delete("athena_import_progress")

    def test_can_trigger_import_when_none_in_progress(
        self, api_client: APIClient, admin_user: "UserType", monkeypatch
    ) -> None:
        """
        Test that import can be triggered when no import is in progress.

        Requirements: 1.5
        """
        from unittest.mock import Mock

        # Ensure no import in progress
        cache.delete("athena_import_progress")

        # Mock the Celery task to avoid actual execution
        mock_task = Mock()
        mock_task.delay = Mock(return_value=Mock(id="test-task-id"))

        def mock_import_task(*args, **kwargs):
            return mock_task

        # Mock the import task
        import trading.athena_import_task

        monkeypatch.setattr(trading.athena_import_task, "import_athena_data_daily", mock_task)

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_trigger_athena_import")

        response = api_client.post(
            url,
            {
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-01T00:00:00Z",
            },
            format="json",
        )

        # Should succeed (200 or 202)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_202_ACCEPTED]
        assert response.data["success"] is True

        # Clean up
        cache.delete("athena_import_progress")

    def test_can_trigger_after_previous_import_completed(
        self, api_client: APIClient, admin_user: "UserType", monkeypatch
    ) -> None:
        """
        Test that import can be triggered after previous import completed.

        Requirements: 1.5
        """
        from unittest.mock import Mock

        # Set up a completed import
        completed_data = {
            "in_progress": False,
            "current_day": 5,
            "total_days": 5,
            "percentage": 100.0,
            "status": "completed",
            "message": "Import completed successfully",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-05T00:00:00Z",
            "started_at": "2024-01-06T10:00:00Z",
            "completed_at": "2024-01-06T11:00:00Z",
            "error": None,
        }
        cache.set("athena_import_progress", completed_data, timeout=3600)

        # Mock the Celery task
        mock_task = Mock()
        mock_task.delay = Mock(return_value=Mock(id="test-task-id"))

        import trading.athena_import_task

        monkeypatch.setattr(trading.athena_import_task, "import_athena_data_daily", mock_task)

        api_client.force_authenticate(user=admin_user)
        url = reverse("accounts:admin_trigger_athena_import")

        response = api_client.post(
            url,
            {
                "start_date": "2024-01-10T00:00:00Z",
                "end_date": "2024-01-10T00:00:00Z",
            },
            format="json",
        )

        # Should succeed since previous import is completed
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_202_ACCEPTED]
        assert response.data["success"] is True

        # Clean up
        cache.delete("athena_import_progress")


@pytest.mark.django_db
class TestImportAthenaDataDailyProgressTracking:
    """Test suite for progress tracking in import_athena_data_daily task."""

    def test_progress_initialization(self) -> None:
        """
        Test that progress is incremented at the start of each day's import.

        Requirements: 2.2
        """
        from trading.athena_import_task import _increment_progress, _update_progress_state

        # Initialize progress state
        _update_progress_state(
            {
                "in_progress": True,
                "current_day": 0,
                "total_days": 3,
                "status": "running",
                "message": "Starting import...",
            }
        )

        # Increment progress (simulating first day starting)
        _increment_progress()

        # Check progress was updated
        progress = cache.get("athena_import_progress")
        assert progress is not None
        assert progress["current_day"] == 1
        assert progress["total_days"] == 3
        assert progress["percentage"] == pytest.approx(33.33, rel=0.1)
        assert "day 1 of 3" in progress["message"]

        # Clean up
        cache.delete("athena_import_progress")

    def test_progress_updates_after_each_day(self) -> None:
        """
        Test that progress updates correctly after each day completes.

        Requirements: 2.2
        """
        from trading.athena_import_task import _increment_progress, _update_progress_state

        # Initialize progress
        _update_progress_state(
            {
                "in_progress": True,
                "current_day": 0,
                "total_days": 5,
                "status": "running",
            }
        )

        # Simulate processing 3 days
        for expected_day in range(1, 4):
            _increment_progress()
            progress = cache.get("athena_import_progress")
            assert progress["current_day"] == expected_day
            assert progress["total_days"] == 5
            expected_percentage = (expected_day / 5) * 100
            assert progress["percentage"] == pytest.approx(expected_percentage, rel=0.1)
            assert f"day {expected_day} of 5" in progress["message"]

        # Clean up
        cache.delete("athena_import_progress")

    def test_completion_marking(self) -> None:
        """
        Test that import is marked as completed when all days are processed.

        Requirements: 2.2
        """
        from trading.athena_import_task import _update_progress_state

        # Set up progress at the last day
        _update_progress_state(
            {
                "in_progress": True,
                "current_day": 7,
                "total_days": 7,
                "status": "running",
            }
        )

        # Mark as completed
        _update_progress_state(
            {
                "status": "completed",
                "message": "Import completed successfully (7 days)",
                "completed_at": "2024-01-08T12:00:00Z",
            }
        )

        # Check completion status
        progress = cache.get("athena_import_progress")
        assert progress is not None
        assert progress["status"] == "completed"
        assert progress["current_day"] == 7
        assert progress["total_days"] == 7
        assert progress["percentage"] == 100.0
        assert "completed successfully" in progress["message"]
        assert progress["completed_at"] is not None

        # Clean up
        cache.delete("athena_import_progress")

    def test_failure_handling(self) -> None:
        """
        Test that import failure is properly recorded in progress state.

        Requirements: 2.2
        """
        from trading.athena_import_task import _update_progress_state

        # Set up progress mid-import
        _update_progress_state(
            {
                "in_progress": True,
                "current_day": 3,
                "total_days": 7,
                "status": "running",
            }
        )

        # Mark as failed
        error_message = "Database connection timeout"
        _update_progress_state(
            {
                "status": "failed",
                "message": "Import failed",
                "error": error_message,
                "completed_at": "2024-01-08T11:30:00Z",
            }
        )

        # Check failure status
        progress = cache.get("athena_import_progress")
        assert progress is not None
        assert progress["status"] == "failed"
        assert progress["error"] == error_message
        assert progress["current_day"] == 3
        assert progress["total_days"] == 7
        assert progress["completed_at"] is not None

        # Clean up
        cache.delete("athena_import_progress")

    def test_percentage_calculation(self) -> None:
        """
        Test that percentage is calculated correctly.

        Requirements: 2.2
        """
        from trading.athena_import_task import _update_progress_state

        # Test various progress points
        test_cases = [
            (1, 10, 10.0),
            (5, 10, 50.0),
            (7, 10, 70.0),
            (10, 10, 100.0),
            (3, 7, 42.857),
        ]

        for current_day, total_days, expected_percentage in test_cases:
            _update_progress_state(
                {
                    "current_day": current_day,
                    "total_days": total_days,
                }
            )

            progress = cache.get("athena_import_progress")
            assert progress is not None
            assert progress["percentage"] == pytest.approx(expected_percentage, rel=0.01)

        # Clean up
        cache.delete("athena_import_progress")

    def test_progress_with_zero_total_days(self) -> None:
        """
        Test that progress handles edge case of zero total days gracefully.

        Requirements: 2.2
        """
        from trading.athena_import_task import _update_progress_state

        # Set up progress with zero total days (edge case)
        _update_progress_state(
            {
                "current_day": 0,
                "total_days": 0,
            }
        )

        progress = cache.get("athena_import_progress")
        assert progress is not None
        assert progress["percentage"] == 0

        # Clean up
        cache.delete("athena_import_progress")
