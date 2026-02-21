"""Pytest fixtures for market unit tests."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from apps.accounts.models import User as UserType
else:
    UserType = object

User = get_user_model()


@pytest.fixture
def user(db) -> "UserType":
    """Create a test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]
        email="test@example.com",
        password="testpass123",
        username="testuser",
    )


@pytest.fixture
def another_user(db) -> "UserType":
    """Create another test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]
        email="another@example.com",
        password="testpass123",
        username="anotheruser",
    )
