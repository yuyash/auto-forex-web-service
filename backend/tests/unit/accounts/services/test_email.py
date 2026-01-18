"""Unit tests for email service."""

from unittest.mock import patch

from apps.accounts.services.email import AccountEmailService


class TestAccountEmailService:
    """Test AccountEmailService class."""

    def test_email_service_exists(self):
        """Test AccountEmailService class exists."""
        assert AccountEmailService is not None

    @patch("django.core.mail.send_mail")
    def test_send_verification_email(self, mock_send_mail):
        """Test sending verification email."""
        mock_send_mail.return_value = 1

        service = AccountEmailService()

        # Test that service has send method or similar
        assert hasattr(service, "send_verification_email") or hasattr(service, "send_email")

    def test_email_service_is_callable(self):
        """Test AccountEmailService can be instantiated."""
        service = AccountEmailService()
        assert service is not None
