"""Unit tests for email verification views."""

from unittest.mock import patch

import pytest
from django.test import RequestFactory
from rest_framework import status

from apps.accounts.models import User
from apps.accounts.views.verification import EmailVerificationView, ResendVerificationEmailView


@pytest.mark.django_db
class TestEmailVerificationView:
    """Tests for EmailVerificationView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = EmailVerificationView.as_view()

    def test_successful_verification(self) -> None:
        """Test successful email verification."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )
        token = user.generate_verification_token()

        data = {"token": token}
        request = self.factory.post("/api/auth/verify-email", data, content_type="application/json")

        with patch("apps.accounts.views.verification.AccountEmailService") as mock_email:
            mock_email.return_value.send_welcome_message.return_value = True
            response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.email_verified is True

    def test_verification_missing_token(self) -> None:
        """Test verification without token."""
        data = {}
        request = self.factory.post("/api/auth/verify-email", data, content_type="application/json")
        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verification_invalid_token(self) -> None:
        """Test verification with invalid token."""
        data = {"token": "invalid_token"}
        request = self.factory.post("/api/auth/verify-email", data, content_type="application/json")
        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestResendVerificationEmailView:
    """Tests for ResendVerificationEmailView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = ResendVerificationEmailView.as_view()

    def test_resend_verification_email(self) -> None:
        """Test resending verification email."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )
        user.email_verified = False
        user.save()

        data = {"email": "test@example.com"}
        request = self.factory.post(
            "/api/auth/resend-verification", data, content_type="application/json"
        )

        with patch("apps.accounts.views.verification.AccountEmailService") as mock_email:
            mock_email.return_value.send_verification_email.return_value = True
            response = self.view(request)

        assert response.status_code == status.HTTP_200_OK

    def test_resend_already_verified(self) -> None:
        """Test resending verification email for already verified user."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )
        user.email_verified = True
        user.save()

        data = {"email": "test@example.com"}
        request = self.factory.post(
            "/api/auth/resend-verification", data, content_type="application/json"
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_resend_nonexistent_email(self) -> None:
        """Test resending verification email for nonexistent email."""
        data = {"email": "nonexistent@example.com"}
        request = self.factory.post(
            "/api/auth/resend-verification", data, content_type="application/json"
        )
        response = self.view(request)

        # Should return 200 to avoid revealing if email exists
        assert response.status_code == status.HTTP_200_OK
