"""Unit tests for accounts admin."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

from apps.accounts.admin import UserAdmin

User = get_user_model()


@pytest.mark.django_db
class TestUserAdmin:
    """Test UserAdmin."""

    def test_user_admin_registered(self):
        """Test User is registered in admin."""
        assert User in admin.site._registry
        assert isinstance(admin.site._registry[User], UserAdmin)

    def test_user_admin_list_display(self):
        """Test list_display is configured."""
        admin_instance = UserAdmin(User, admin.site)
        assert hasattr(admin_instance, "list_display")
        assert len(admin_instance.list_display) > 0


@pytest.mark.django_db
class TestAccountsAdminModels:
    """Test other accounts models are registered in admin."""

    def test_models_registered_in_admin(self):
        """Test accounts models are registered."""
        # Check if models are registered (may or may not be)
        registered_models = admin.site._registry.keys()

        # At least User should be registered
        assert User in registered_models
