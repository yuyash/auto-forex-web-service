"""Unit tests for AccountEmailService (mocked dependencies)."""

from unittest.mock import MagicMock, patch

from apps.accounts.services.email import AccountEmailService


class TestAccountEmailService:
    """Unit tests for AccountEmailService."""

    def test_send_verification_email(self) -> None:
        """Test sending verification email."""
        service = AccountEmailService()
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"

        with patch.object(service, "_send_email") as mock_send:
            mock_send.return_value = True

            result = service.send_verification_email(
                user=mock_user,
                verification_url="https://example.com/verify?token=abc",
                sender=None,
            )

        assert result is True
        mock_send.assert_called_once()

    def test_send_verification_email_failure(self) -> None:
        """Test handling verification email send failure."""
        service = AccountEmailService()
        mock_user = MagicMock()
        mock_user.email = "test@example.com"

        with patch.object(service, "_send_email") as mock_send:
            mock_send.return_value = False

            result = service.send_verification_email(
                user=mock_user,
                verification_url="https://example.com/verify?token=abc",
                sender=None,
            )

        assert result is False

    def test_send_welcome_message(self) -> None:
        """Test sending welcome message."""
        service = AccountEmailService()
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"

        with patch.object(service, "_send_email") as mock_send:
            mock_send.return_value = True

            result = service.send_welcome_message(
                user=mock_user,
                sender=None,
            )

        assert result is True
        mock_send.assert_called_once()
