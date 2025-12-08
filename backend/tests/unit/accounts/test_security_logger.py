"""
Unit tests for security event logger.

Tests cover:
- Security event signal sending
- Login success/failure logging
- Account locking events
- IP blocking events
- Configuration change events
- Unauthorized access attempts
- Suspicious pattern detection
"""

from unittest.mock import MagicMock, patch

from apps.accounts.security_logger import SecurityEventLogger, security_event


class TestSecurityEventSignal:
    """Test cases for security_event signal."""

    def test_signal_exists(self) -> None:
        """Test that security_event signal is defined."""
        assert security_event is not None

    @patch.object(security_event, "send")
    def test_signal_can_be_sent(self, mock_send: MagicMock) -> None:
        """Test that signal can be sent."""
        security_event.send(
            sender=SecurityEventLogger,
            event_type="test",
            category="security",
            description="Test event",
            severity="info",
        )

        mock_send.assert_called_once()


class TestSecurityEventLoggerSendEvent:
    """Test cases for _send_event method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_send_event_with_all_parameters(self, mock_send: MagicMock) -> None:
        """Test _send_event sends signal with all parameters."""
        mock_user = MagicMock()

        self.logger._send_event(
            event_type="test_event",
            description="Test description",
            severity="warning",
            user=mock_user,
            ip_address="192.168.1.1",
            user_agent="Test Agent",
            details={"key": "value"},
        )

        mock_send.assert_called_once_with(
            sender=SecurityEventLogger,
            event_type="test_event",
            category="security",
            description="Test description",
            severity="warning",
            user=mock_user,
            ip_address="192.168.1.1",
            user_agent="Test Agent",
            details={"key": "value"},
        )

    @patch.object(security_event, "send")
    def test_send_event_with_minimal_parameters(self, mock_send: MagicMock) -> None:
        """Test _send_event with minimal parameters."""
        self.logger._send_event(
            event_type="test_event",
            description="Test description",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "test_event"
        assert call_kwargs["description"] == "Test description"
        assert call_kwargs["severity"] == "info"
        assert call_kwargs["details"] == {}

    @patch.object(security_event, "send")
    def test_send_event_defaults_details_to_empty_dict(self, mock_send: MagicMock) -> None:
        """Test _send_event defaults details to empty dict."""
        self.logger._send_event(
            event_type="test",
            description="Test",
            details=None,
        )

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["details"] == {}


class TestLogLoginSuccess:
    """Test cases for log_login_success method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_login_success(self, mock_send: MagicMock) -> None:
        """Test log_login_success sends correct event."""
        mock_user = MagicMock()
        mock_user.username = "testuser"

        self.logger.log_login_success(
            user=mock_user,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "login_success"
        assert call_kwargs["severity"] == "info"
        assert "testuser" in call_kwargs["description"]
        assert call_kwargs["user"] == mock_user
        assert call_kwargs["ip_address"] == "192.168.1.1"

    @patch.object(security_event, "send")
    def test_log_login_success_with_extra_kwargs(self, mock_send: MagicMock) -> None:
        """Test log_login_success passes extra kwargs to details."""
        mock_user = MagicMock()
        mock_user.username = "testuser"

        self.logger.log_login_success(
            user=mock_user,
            ip_address="192.168.1.1",
            method="password",
            session_id="abc123",
        )

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["details"]["method"] == "password"
        assert call_kwargs["details"]["session_id"] == "abc123"


class TestLogLoginFailed:
    """Test cases for log_login_failed method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_login_failed(self, mock_send: MagicMock) -> None:
        """Test log_login_failed sends correct event."""
        self.logger.log_login_failed(
            username="testuser",
            ip_address="192.168.1.1",
            reason="Invalid password",
            user_agent="Mozilla/5.0",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "login_failed"
        assert call_kwargs["severity"] == "warning"
        assert "testuser" in call_kwargs["description"]
        assert "Invalid password" in call_kwargs["description"]
        assert call_kwargs["ip_address"] == "192.168.1.1"

    @patch.object(security_event, "send")
    def test_log_login_failed_details_include_reason(self, mock_send: MagicMock) -> None:
        """Test log_login_failed includes reason in details."""
        self.logger.log_login_failed(
            username="testuser",
            ip_address="192.168.1.1",
            reason="Account locked",
        )

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["details"]["username"] == "testuser"
        assert call_kwargs["details"]["reason"] == "Account locked"


class TestLogLogout:
    """Test cases for log_logout method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_logout(self, mock_send: MagicMock) -> None:
        """Test log_logout sends correct event."""
        mock_user = MagicMock()
        mock_user.username = "testuser"

        self.logger.log_logout(
            user=mock_user,
            ip_address="192.168.1.1",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "logout"
        assert call_kwargs["severity"] == "info"
        assert "testuser" in call_kwargs["description"]
        assert call_kwargs["user"] == mock_user


class TestLogAccountLocked:
    """Test cases for log_account_locked method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_account_locked(self, mock_send: MagicMock) -> None:
        """Test log_account_locked sends correct event."""
        self.logger.log_account_locked(
            username="testuser",
            ip_address="192.168.1.1",
            failed_attempts=10,
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "account_locked"
        assert call_kwargs["severity"] == "error"
        assert "testuser" in call_kwargs["description"]
        assert "10" in call_kwargs["description"]
        assert call_kwargs["details"]["failed_attempts"] == 10


class TestLogIPBlocked:
    """Test cases for log_ip_blocked method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_ip_blocked(self, mock_send: MagicMock) -> None:
        """Test log_ip_blocked sends correct event."""
        self.logger.log_ip_blocked(
            ip_address="192.168.1.1",
            failed_attempts=5,
            duration_seconds=3600,
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "ip_blocked"
        assert call_kwargs["severity"] == "warning"
        assert "192.168.1.1" in call_kwargs["description"]
        assert "3600" in call_kwargs["description"]
        assert call_kwargs["details"]["failed_attempts"] == 5
        assert call_kwargs["details"]["duration_seconds"] == 3600


class TestLogAccountCreated:
    """Test cases for log_account_created method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_account_created(self, mock_send: MagicMock) -> None:
        """Test log_account_created sends correct event."""
        self.logger.log_account_created(
            username="newuser",
            email="newuser@example.com",
            ip_address="192.168.1.1",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "account_created"
        assert call_kwargs["severity"] == "info"
        assert "newuser" in call_kwargs["description"]
        assert "newuser@example.com" in call_kwargs["description"]
        assert call_kwargs["details"]["username"] == "newuser"
        assert call_kwargs["details"]["email"] == "newuser@example.com"


class TestLogConfigChanged:
    """Test cases for log_config_changed method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_config_changed(self, mock_send: MagicMock) -> None:
        """Test log_config_changed sends correct event."""
        mock_user = MagicMock()
        mock_user.username = "admin"

        self.logger.log_config_changed(
            user=mock_user,
            config_type="security_settings",
            changed_parameters={"max_attempts": 5},
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "config_changed"
        assert call_kwargs["severity"] == "info"
        assert "admin" in call_kwargs["description"]
        assert "security_settings" in call_kwargs["description"]
        assert call_kwargs["details"]["config_type"] == "security_settings"
        assert call_kwargs["details"]["changed_parameters"] == {"max_attempts": 5}


class TestLogUnauthorizedAccessAttempt:
    """Test cases for log_unauthorized_access_attempt method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_unauthorized_access_with_user(self, mock_send: MagicMock) -> None:
        """Test log_unauthorized_access_attempt with authenticated user."""
        mock_user = MagicMock()
        mock_user.username = "hacker"

        self.logger.log_unauthorized_access_attempt(
            user=mock_user,
            resource="/admin/users",
            ip_address="192.168.1.1",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "unauthorized_access_attempt"
        assert call_kwargs["severity"] == "warning"
        assert "hacker" in call_kwargs["description"]
        assert "/admin/users" in call_kwargs["description"]

    @patch.object(security_event, "send")
    def test_log_unauthorized_access_anonymous(self, mock_send: MagicMock) -> None:
        """Test log_unauthorized_access_attempt with anonymous user."""
        self.logger.log_unauthorized_access_attempt(
            user=None,
            resource="/admin/users",
            ip_address="192.168.1.1",
        )

        call_kwargs = mock_send.call_args[1]
        assert "anonymous" in call_kwargs["description"]


class TestLogSuspiciousPattern:
    """Test cases for log_suspicious_pattern method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_suspicious_pattern(self, mock_send: MagicMock) -> None:
        """Test log_suspicious_pattern sends correct event."""
        self.logger.log_suspicious_pattern(
            pattern_type="brute_force",
            description="Multiple failed logins from same IP",
            ip_address="192.168.1.1",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "suspicious_pattern"
        assert call_kwargs["severity"] == "warning"
        assert "Multiple failed logins" in call_kwargs["description"]
        assert call_kwargs["details"]["pattern_type"] == "brute_force"


class TestLogSecurityEvent:
    """Test cases for log_security_event generic method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = SecurityEventLogger()

    @patch.object(security_event, "send")
    def test_log_security_event(self, mock_send: MagicMock) -> None:
        """Test log_security_event sends correct event."""
        mock_user = MagicMock()

        self.logger.log_security_event(
            event_type="custom_event",
            description="Custom security event",
            severity="critical",
            user=mock_user,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            details={"custom_field": "value"},
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["event_type"] == "custom_event"
        assert call_kwargs["description"] == "Custom security event"
        assert call_kwargs["severity"] == "critical"
        assert call_kwargs["user"] == mock_user
        assert call_kwargs["details"]["custom_field"] == "value"

    @patch.object(security_event, "send")
    def test_log_security_event_defaults(self, mock_send: MagicMock) -> None:
        """Test log_security_event with default values."""
        self.logger.log_security_event(
            event_type="test_event",
            description="Test",
        )

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["severity"] == "info"
        assert call_kwargs["user"] is None
        assert call_kwargs["ip_address"] is None
        assert call_kwargs["user_agent"] is None
        # details defaults to empty dict, not None
        assert call_kwargs["details"] == {}
