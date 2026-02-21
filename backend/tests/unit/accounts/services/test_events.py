"""Unit tests for SecurityEventService (mocked dependencies)."""

from unittest.mock import MagicMock, patch

from apps.accounts.services.events import (
    EventSeverity,
    EventType,
    SecurityEvent,
    SecurityEventService,
)


class TestSecurityEvent:
    """Unit tests for SecurityEvent dataclass."""

    def test_create_security_event(self) -> None:
        """Test creating a security event."""
        event = SecurityEvent(
            event_type=EventType.LOGIN_SUCCESS,
            description="Test event",
            severity=EventSeverity.INFO,
        )

        assert event.event_type == EventType.LOGIN_SUCCESS
        assert event.description == "Test event"
        assert event.severity == EventSeverity.INFO

    def test_to_dict(self) -> None:
        """Test converting event to dictionary."""
        mock_user = MagicMock()
        mock_user.pk = 1

        event = SecurityEvent(
            event_type=EventType.LOGIN_SUCCESS,
            description="Test event",
            severity=EventSeverity.INFO,
            user=mock_user,
            ip_address="127.0.0.1",
            user_agent="Test Agent",
            details={"key": "value"},
        )

        result = event.to_dict()

        assert result["event_type"] == "login_success"
        assert result["severity"] == "info"
        assert result["description"] == "Test event"
        assert result["user"] == mock_user
        assert result["ip_address"] == "127.0.0.1"
        assert result["user_agent"] == "Test Agent"
        assert result["details"] == {"key": "value"}


class TestSecurityEventService:
    """Unit tests for SecurityEventService."""

    def test_log_event_success(self) -> None:
        """Test logging an event successfully."""
        service = SecurityEventService()
        event = SecurityEvent(
            event_type=EventType.LOGIN_SUCCESS,
            description="Test",
        )

        with patch(
            "apps.accounts.services.events.AccountSecurityEvent.objects.create"
        ) as mock_create:
            service.log_event(event)

        mock_create.assert_called_once()

    def test_log_event_handles_exception(self) -> None:
        """Test log_event handles exceptions gracefully."""
        service = SecurityEventService()
        event = SecurityEvent(
            event_type=EventType.LOGIN_SUCCESS,
            description="Test",
        )

        with patch(
            "apps.accounts.services.events.AccountSecurityEvent.objects.create"
        ) as mock_create:
            mock_create.side_effect = Exception("Database error")

            # Should not raise
            service.log_event(event)

    def test_log_login_success(self) -> None:
        """Test logging login success event."""
        service = SecurityEventService()
        mock_user = MagicMock()
        mock_user.username = "testuser"

        with patch.object(service, "log_event") as mock_log:
            service.log_login_success(
                user=mock_user,
                ip_address="127.0.0.1",
                user_agent="Test Agent",
            )

        mock_log.assert_called_once()
        event = mock_log.call_args[0][0]
        assert event.event_type == EventType.LOGIN_SUCCESS
        assert "testuser" in event.description

    def test_log_login_failed(self) -> None:
        """Test logging login failed event."""
        service = SecurityEventService()

        with patch.object(service, "log_event") as mock_log:
            service.log_login_failed(
                username="testuser",
                ip_address="127.0.0.1",
                reason="Invalid credentials",
            )

        mock_log.assert_called_once()
        event = mock_log.call_args[0][0]
        assert event.event_type == EventType.LOGIN_FAILED
        assert event.severity == EventSeverity.WARNING

    def test_log_account_created(self) -> None:
        """Test logging account created event."""
        service = SecurityEventService()

        with patch.object(service, "log_event") as mock_log:
            service.log_account_created(
                username="newuser",
                email="new@example.com",
                ip_address="127.0.0.1",
            )

        mock_log.assert_called_once()
        event = mock_log.call_args[0][0]
        assert event.event_type == EventType.ACCOUNT_CREATED
