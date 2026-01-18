"""Unit tests for accounts events service."""

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.services.events import SecurityEventService

User = get_user_model()


class TestSecurityEventService:
    """Test SecurityEventService class."""

    def test_event_service_exists(self):
        """Test SecurityEventService class exists."""
        assert SecurityEventService is not None

    def test_event_service_is_callable(self):
        """Test SecurityEventService can be instantiated."""
        service = SecurityEventService()
        assert service is not None

    @pytest.mark.django_db
    def test_log_event_method_exists(self):
        """Test log_event method exists."""
        service = SecurityEventService()

        # Test that service has logging methods
        assert (
            hasattr(service, "log_login_success")
            or hasattr(service, "log_login_failed")
            or hasattr(service, "_write_event")
        )
