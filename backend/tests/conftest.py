"""
Pytest configuration and fixtures for integration tests.

This module provides shared fixtures for testing Django views via live_server.
"""

from django.contrib.auth import get_user_model

import pytest

User = get_user_model()


@pytest.fixture(autouse=True)
def _mock_ses_email_sending(monkeypatch, settings):
    """Prevent tests from making real AWS SES calls.

    Integration tests hit live endpoints (via live_server) that trigger email sending.
    We stub out the SES client used by apps.accounts.services.email.
    """

    if not getattr(settings, "DEFAULT_FROM_EMAIL", ""):
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"

    import apps.accounts.services.email as email_module

    class _DummySesClient:
        def send_email(self, **_kwargs):
            return {"MessageId": "test-message-id"}

    def _fake_boto3_client(service_name, *_args, **_kwargs):
        if service_name == "ses":
            return _DummySesClient()
        raise AssertionError(f"Unexpected boto3 client requested in tests: {service_name}")

    monkeypatch.setattr(email_module.boto3, "client", _fake_boto3_client)


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix):
    """Use parallel suffix for database in parallel test execution."""
    pass


@pytest.fixture
def test_user(db):
    """Create a test user for authentication tests."""
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="TestPass123!",
    )
    user.email_verified = True
    user.save()
    return user


@pytest.fixture
def unverified_user(db):
    """Create an unverified test user."""
    user = User.objects.create_user(
        username="unverified",
        email="unverified@example.com",
        password="TestPass123!",
    )
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin user for privileged endpoint tests."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="AdminPass123!",
    )
    user.email_verified = True
    user.save()
    return user


@pytest.fixture
def locked_user(db):
    """Create a locked user account."""
    user = User.objects.create_user(
        username="locked",
        email="locked@example.com",
        password="TestPass123!",
    )
    user.email_verified = True
    user.is_locked = True
    user.failed_login_attempts = 10
    user.save()
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generate authorization headers for authenticated requests."""
    from apps.accounts.services.jwt import JWTService

    token = JWTService().generate_token(test_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user):
    """Generate authorization headers for admin requests."""
    from apps.accounts.services.jwt import JWTService

    token = JWTService().generate_token(admin_user)
    return {"Authorization": f"Bearer {token}"}
