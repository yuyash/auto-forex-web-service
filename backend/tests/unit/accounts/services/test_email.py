"""Unit tests for apps.accounts.services.email (AccountEmailService)."""

from unittest.mock import MagicMock, patch

import pytest
from django.test.utils import override_settings

from apps.accounts.services.email import AccountEmailService


class TestAccountEmailServiceSendEmail:
    def test_send_email_returns_false_when_default_from_empty(self) -> None:
        service = AccountEmailService()

        with override_settings(DEFAULT_FROM_EMAIL=""):
            with patch("apps.accounts.services.email.boto3.client") as boto_client:
                ok = service._send_email(
                    to_address="to@example.com",
                    subject="Subject",
                    html_body="<b>Hi</b>",
                    text_body="Hi",
                )

        assert ok is False
        boto_client.assert_not_called()

    def test_send_email_calls_ses_send_email(self) -> None:
        service = AccountEmailService()

        mock_ses = MagicMock()

        with override_settings(DEFAULT_FROM_EMAIL="noreply@example.com"):
            with patch("apps.accounts.services.email.boto3.client", return_value=mock_ses) as boto_client:
                ok = service._send_email(
                    to_address="to@example.com",
                    subject="Hello",
                    html_body="<b>Hello</b>",
                    text_body="Hello",
                )

        assert ok is True
        boto_client.assert_called_once_with("ses")
        mock_ses.send_email.assert_called_once()
        kwargs = mock_ses.send_email.call_args.kwargs
        assert kwargs["Source"] == "noreply@example.com"
        assert kwargs["Destination"] == {"ToAddresses": ["to@example.com"]}
        assert kwargs["Message"]["Subject"]["Data"] == "Hello"

    def test_send_email_returns_false_on_exception(self) -> None:
        service = AccountEmailService()

        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = RuntimeError("boom")

        with override_settings(DEFAULT_FROM_EMAIL="noreply@example.com"):
            with patch("apps.accounts.services.email.boto3.client", return_value=mock_ses):
                ok = service._send_email(
                    to_address="to@example.com",
                    subject="Hello",
                    html_body="<b>Hello</b>",
                    text_body="Hello",
                )

        assert ok is False


@pytest.mark.django_db
class TestAccountEmailServiceTemplates:
    def test_send_verification_email_invokes_send(self) -> None:
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPass123!",
        )

        service = AccountEmailService()
        with patch.object(service, "_send_email", return_value=True) as send_email:
            ok = service.send_verification_email(user, "https://example.com/verify")

        assert ok is True
        send_email.assert_called_once()
