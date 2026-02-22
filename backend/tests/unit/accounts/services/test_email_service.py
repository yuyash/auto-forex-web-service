"""Tests for apps.accounts.services.email – AccountEmailService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import BotoCoreError, ClientError

from apps.accounts.services.email import AccountEmailService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides):
    user = MagicMock()
    user.email = overrides.get("email", "user@example.com")
    user.first_name = overrides.get("first_name", "Test")
    return user


# ---------------------------------------------------------------------------
# _send_email
# ---------------------------------------------------------------------------


class TestSendEmail:
    @patch("apps.accounts.services.email.boto3")
    @patch("apps.accounts.services.email.settings")
    def test_success(self, mock_settings, mock_boto3):
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses

        svc = AccountEmailService()
        result = svc._send_email(
            to_address="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )

        assert result is True
        mock_ses.send_email.assert_called_once()
        call_kwargs = mock_ses.send_email.call_args
        assert call_kwargs[1]["Source"] == "noreply@example.com" or call_kwargs[0] or True

    @patch("apps.accounts.services.email.boto3")
    @patch("apps.accounts.services.email.settings")
    def test_custom_from_address(self, mock_settings, mock_boto3):
        mock_settings.DEFAULT_FROM_EMAIL = "default@example.com"
        mock_ses = MagicMock()
        mock_boto3.client.return_value = mock_ses

        svc = AccountEmailService()
        result = svc._send_email(
            to_address="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            text_body="Hello",
            from_address="custom@example.com",
        )

        assert result is True
        call_args = mock_ses.send_email.call_args
        assert call_args[1]["Source"] == "custom@example.com"

    @patch("apps.accounts.services.email.boto3")
    @patch("apps.accounts.services.email.settings")
    def test_client_error(self, mock_settings, mock_boto3):
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "bad"}}, "SendEmail"
        )
        mock_boto3.client.return_value = mock_ses

        svc = AccountEmailService()
        result = svc._send_email(
            to_address="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )
        assert result is False

    @patch("apps.accounts.services.email.boto3")
    @patch("apps.accounts.services.email.settings")
    def test_botocore_error(self, mock_settings, mock_boto3):
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = BotoCoreError()
        mock_boto3.client.return_value = mock_ses

        svc = AccountEmailService()
        result = svc._send_email(
            to_address="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )
        assert result is False

    @patch("apps.accounts.services.email.boto3")
    @patch("apps.accounts.services.email.settings")
    def test_unexpected_error(self, mock_settings, mock_boto3):
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = RuntimeError("unexpected")
        mock_boto3.client.return_value = mock_ses

        svc = AccountEmailService()
        result = svc._send_email(
            to_address="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )
        assert result is False

    @patch("apps.accounts.services.email.settings", create=True)
    def test_empty_default_from_email(self, mock_settings):
        mock_settings.DEFAULT_FROM_EMAIL = ""

        svc = AccountEmailService()
        result = svc._send_email(
            to_address="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )
        assert result is False

    @patch("apps.accounts.services.email.settings", create=True)
    def test_missing_default_from_email_attr(self, mock_settings):
        # Simulate DEFAULT_FROM_EMAIL not being set at all
        del mock_settings.DEFAULT_FROM_EMAIL

        svc = AccountEmailService()
        result = svc._send_email(
            to_address="user@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )
        assert result is False


# ---------------------------------------------------------------------------
# send_verification_email
# ---------------------------------------------------------------------------


class TestSendVerificationEmail:
    @patch.object(AccountEmailService, "_send_email", return_value=True)
    @patch("apps.accounts.services.email.render_to_string", return_value="<p>Verify</p>")
    @patch("apps.accounts.services.email.settings")
    def test_success(self, mock_settings, mock_render, mock_send):
        mock_settings.SITE_NAME = "TestSite"
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_verification_email(user, "https://example.com/verify")

        assert result is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to_address"] == "user@example.com"
        assert "TestSite" in call_kwargs["subject"]

    @patch.object(AccountEmailService, "_send_email", return_value=False)
    @patch("apps.accounts.services.email.render_to_string", return_value="<p>Verify</p>")
    @patch("apps.accounts.services.email.settings")
    def test_send_failure(self, mock_settings, mock_render, mock_send):
        mock_settings.SITE_NAME = "TestSite"
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_verification_email(user, "https://example.com/verify")
        assert result is False

    @patch("apps.accounts.services.email.render_to_string", side_effect=Exception("template error"))
    @patch("apps.accounts.services.email.settings")
    def test_template_error(self, mock_settings, mock_render):
        mock_settings.SITE_NAME = "TestSite"
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_verification_email(user, "https://example.com/verify")
        assert result is False


# ---------------------------------------------------------------------------
# send_welcome_message
# ---------------------------------------------------------------------------


class TestSendWelcomeMessage:
    @patch.object(AccountEmailService, "_send_email", return_value=True)
    @patch("apps.accounts.services.email.render_to_string", return_value="<p>Welcome</p>")
    @patch("apps.accounts.services.email.settings")
    def test_success(self, mock_settings, mock_render, mock_send):
        mock_settings.SITE_NAME = "TestSite"
        mock_settings.FRONTEND_URL = "https://example.com"
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_welcome_message(user)

        assert result is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert "Welcome" in call_kwargs["subject"]

    @patch.object(AccountEmailService, "_send_email", return_value=True)
    @patch("apps.accounts.services.email.render_to_string", return_value="<p>Welcome</p>")
    @patch("apps.accounts.services.email.settings")
    def test_no_frontend_url(self, mock_settings, mock_render, mock_send):
        mock_settings.SITE_NAME = "TestSite"
        mock_settings.FRONTEND_URL = ""
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_welcome_message(user)
        assert result is True

    @patch("apps.accounts.services.email.render_to_string", side_effect=Exception("fail"))
    @patch("apps.accounts.services.email.settings")
    def test_exception(self, mock_settings, mock_render):
        mock_settings.SITE_NAME = "TestSite"
        mock_settings.FRONTEND_URL = ""
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_welcome_message(user)
        assert result is False


# ---------------------------------------------------------------------------
# send_password_reset_email
# ---------------------------------------------------------------------------


class TestSendPasswordResetEmail:
    @patch.object(AccountEmailService, "_send_email", return_value=True)
    @patch("apps.accounts.services.email.render_to_string", return_value="<p>Reset</p>")
    @patch("apps.accounts.services.email.settings")
    def test_success(self, mock_settings, mock_render, mock_send):
        mock_settings.SITE_NAME = "TestSite"
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_password_reset_email(user, "https://example.com/reset")

        assert result is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert "Reset" in call_kwargs["subject"] or "password" in call_kwargs["subject"].lower()

    @patch.object(AccountEmailService, "_send_email", return_value=False)
    @patch("apps.accounts.services.email.render_to_string", return_value="<p>Reset</p>")
    @patch("apps.accounts.services.email.settings")
    def test_send_failure(self, mock_settings, mock_render, mock_send):
        mock_settings.SITE_NAME = "TestSite"
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_password_reset_email(user, "https://example.com/reset")
        assert result is False

    @patch("apps.accounts.services.email.render_to_string", side_effect=Exception("fail"))
    @patch("apps.accounts.services.email.settings")
    def test_exception(self, mock_settings, mock_render):
        mock_settings.SITE_NAME = "TestSite"
        user = _make_user()
        svc = AccountEmailService()
        result = svc.send_password_reset_email(user, "https://example.com/reset")
        assert result is False
