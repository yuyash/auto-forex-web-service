"""
Pytest configuration and fixtures for integration tests.

This module provides shared fixtures for testing Django views via live_server.
"""

from django.contrib.auth import get_user_model

import pytest

User = get_user_model()


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
    from apps.accounts.jwt_utils import generate_jwt_token

    token = generate_jwt_token(test_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user):
    """Generate authorization headers for admin requests."""
    from apps.accounts.jwt_utils import generate_jwt_token

    token = generate_jwt_token(admin_user)
    return {"Authorization": f"Bearer {token}"}
