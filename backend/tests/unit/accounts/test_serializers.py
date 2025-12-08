"""
Unit tests for account serializers.

Tests cover:
- UserRegistrationSerializer validation and creation
- UserLoginSerializer validation
- UserSettingsSerializer
- UserProfileSerializer validation
- WhitelistedEmailSerializer validation
- PublicAccountSettingsSerializer
"""

import pytest
from rest_framework.exceptions import ValidationError

from apps.accounts.serializers import (
    PublicAccountSettingsSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserSettingsSerializer,
    WhitelistedEmailSerializer,
)


class TestUserRegistrationSerializerValidation:
    """Test cases for UserRegistrationSerializer validation."""

    def test_validate_username_valid_alphanumeric(self) -> None:
        """Test username validation with valid alphanumeric characters."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_username("testuser123")
        assert result == "testuser123"

    def test_validate_username_with_underscore(self) -> None:
        """Test username validation with underscore."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_username("test_user")
        assert result == "test_user"

    def test_validate_username_with_period(self) -> None:
        """Test username validation with period."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_username("test.user")
        assert result == "test.user"

    def test_validate_username_with_dash(self) -> None:
        """Test username validation with dash."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_username("test-user")
        assert result == "test-user"

    def test_validate_username_empty_returns_empty(self) -> None:
        """Test username validation with empty string returns empty."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_username("")
        assert result == ""

    def test_validate_username_invalid_characters_raises(self) -> None:
        """Test username validation raises error for invalid characters."""
        serializer = UserRegistrationSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_username("test@user")
        assert "letters, numbers, underscores, periods, and dashes" in str(exc_info.value)

    def test_validate_username_with_space_raises(self) -> None:
        """Test username validation raises error for spaces."""
        serializer = UserRegistrationSerializer()
        with pytest.raises(ValidationError):
            serializer.validate_username("test user")

    def test_validate_username_too_short_raises(self) -> None:
        """Test username validation raises error for too short username."""
        serializer = UserRegistrationSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_username("ab")
        assert "at least 3 characters" in str(exc_info.value)

    def test_validate_username_too_long_raises(self) -> None:
        """Test username validation raises error for too long username."""
        serializer = UserRegistrationSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_username("a" * 151)
        assert "not exceed 150 characters" in str(exc_info.value)

    @pytest.mark.django_db
    def test_validate_email_valid(self) -> None:
        """Test email validation with valid email."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_email("test@example.com")
        assert result == "test@example.com"

    @pytest.mark.django_db
    def test_validate_email_normalizes_to_lowercase(self) -> None:
        """Test email validation normalizes to lowercase."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_email("TEST@EXAMPLE.COM")
        assert result == "test@example.com"

    @pytest.mark.django_db
    def test_validate_email_invalid_format_raises(self) -> None:
        """Test email validation raises error for invalid format."""
        serializer = UserRegistrationSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_email("invalid-email")
        assert "valid email address" in str(exc_info.value)

    @pytest.mark.django_db
    def test_validate_email_duplicate_raises(self) -> None:
        """Test email validation raises error for duplicate email."""
        from apps.accounts.models import User

        User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="testpass123",
        )

        serializer = UserRegistrationSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_email("existing@example.com")
        assert "already exists" in str(exc_info.value)

    def test_validate_passwords_match(self) -> None:
        """Test passwords match validation."""
        serializer = UserRegistrationSerializer()
        attrs = {
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        result = serializer.validate(attrs)
        assert result == attrs

    def test_validate_passwords_mismatch_raises(self) -> None:
        """Test passwords mismatch raises error."""
        serializer = UserRegistrationSerializer()
        attrs = {
            "password": "TestPass123!",
            "password_confirm": "DifferentPass!",
        }
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate(attrs)
        assert "do not match" in str(exc_info.value)


@pytest.mark.django_db
class TestUserRegistrationSerializerCreate:
    """Test cases for UserRegistrationSerializer create method."""

    def test_create_user_with_username(self) -> None:
        """Test creating user with provided username."""
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        assert user.email == "newuser@example.com"
        assert user.username == "newuser"
        assert user.check_password("TestPass123!")

    def test_create_user_without_username_generates_from_email(self) -> None:
        """Test creating user without username generates one from email."""
        data = {
            "email": "autogen@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        assert user.email == "autogen@example.com"
        assert user.username == "autogen"

    def test_create_user_generates_unique_username(self) -> None:
        """Test creating user generates unique username when conflict exists."""
        from apps.accounts.models import User

        # Create user with the email local part as username
        User.objects.create_user(
            username="duplicate",
            email="other@example.com",
            password="testpass123",
        )

        data = {
            "email": "duplicate@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        # Username should have a counter appended
        assert user.username.startswith("duplicate")
        assert user.username != "duplicate"

    def test_create_user_filters_invalid_chars_from_email(self) -> None:
        """Test creating user filters invalid characters from email for username."""
        data = {
            "email": "test+alias@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        # '+' should be filtered out
        assert "+" not in user.username
        assert user.username == "testalias"


@pytest.mark.django_db
class TestUserLoginSerializer:
    """Test cases for UserLoginSerializer."""

    def test_validate_valid_credentials(self) -> None:
        """Test validation with valid credentials."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="loginuser",
            email="login@example.com",
            password="TestPass123!",
        )

        serializer = UserLoginSerializer(
            data={
                "email": "login@example.com",
                "password": "TestPass123!",
            }
        )

        assert serializer.is_valid()
        assert serializer.validated_data["user"] == user

    def test_validate_invalid_password_raises(self) -> None:
        """Test validation with invalid password raises error."""
        from apps.accounts.models import User

        User.objects.create_user(
            username="loginuser",
            email="login@example.com",
            password="TestPass123!",
        )

        serializer = UserLoginSerializer(
            data={
                "email": "login@example.com",
                "password": "WrongPassword!",
            }
        )

        assert not serializer.is_valid()
        assert "Invalid credentials" in str(serializer.errors)

    def test_validate_nonexistent_user_raises(self) -> None:
        """Test validation with nonexistent user raises error."""
        serializer = UserLoginSerializer(
            data={
                "email": "nonexistent@example.com",
                "password": "TestPass123!",
            }
        )

        assert not serializer.is_valid()
        assert "Invalid credentials" in str(serializer.errors)

    def test_validate_inactive_user_raises(self) -> None:
        """Test validation with inactive user raises error."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="inactiveuser",
            email="inactive@example.com",
            password="TestPass123!",
        )
        user.is_active = False
        user.save()

        serializer = UserLoginSerializer(
            data={
                "email": "inactive@example.com",
                "password": "TestPass123!",
            }
        )

        assert not serializer.is_valid()
        # The serializer returns "Invalid credentials" for inactive users
        # to avoid revealing user existence
        assert "invalid" in str(serializer.errors).lower()

    def test_validate_locked_user_raises(self) -> None:
        """Test validation with locked user raises error."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="lockeduser",
            email="locked@example.com",
            password="TestPass123!",
        )
        user.is_locked = True
        user.save()

        serializer = UserLoginSerializer(
            data={
                "email": "locked@example.com",
                "password": "TestPass123!",
            }
        )

        assert not serializer.is_valid()
        assert "locked" in str(serializer.errors)

    def test_validate_empty_email_raises(self) -> None:
        """Test validation with empty email raises error."""
        serializer = UserLoginSerializer(
            data={
                "email": "",
                "password": "TestPass123!",
            }
        )

        assert not serializer.is_valid()

    def test_validate_empty_password_raises(self) -> None:
        """Test validation with empty password raises error."""
        serializer = UserLoginSerializer(
            data={
                "email": "test@example.com",
                "password": "",
            }
        )

        assert not serializer.is_valid()


@pytest.mark.django_db
class TestUserSettingsSerializer:
    """Test cases for UserSettingsSerializer."""

    def test_serializer_fields(self) -> None:
        """Test serializer contains expected fields."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="settingsuser",
            email="settings@example.com",
            password="testpass123",
        )
        settings = user.settings

        serializer = UserSettingsSerializer(settings)
        data = serializer.data

        assert "id" in data
        assert "notification_enabled" in data
        assert "notification_email" in data
        assert "notification_browser" in data
        assert "settings_json" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_serializer_read_only_fields(self) -> None:
        """Test read-only fields cannot be modified."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="readonlyuser",
            email="readonly@example.com",
            password="testpass123",
        )
        settings = user.settings

        serializer = UserSettingsSerializer(
            settings,
            data={"id": 999, "notification_enabled": False},
            partial=True,
        )
        assert serializer.is_valid()
        updated = serializer.save()

        # ID should not change
        assert updated.id != 999
        # Notification should change
        assert updated.notification_enabled is False


class TestUserProfileSerializer:
    """Test cases for UserProfileSerializer."""

    def test_validate_timezone_valid(self) -> None:
        """Test timezone validation with valid timezone."""
        serializer = UserProfileSerializer()
        result = serializer.validate_timezone("America/New_York")
        assert result == "America/New_York"

    def test_validate_timezone_utc(self) -> None:
        """Test timezone validation with UTC."""
        serializer = UserProfileSerializer()
        result = serializer.validate_timezone("UTC")
        assert result == "UTC"

    def test_validate_timezone_invalid_raises(self) -> None:
        """Test timezone validation raises error for invalid timezone."""
        serializer = UserProfileSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_timezone("Invalid/Timezone")
        assert "not a valid IANA timezone" in str(exc_info.value)

    def test_validate_language_english(self) -> None:
        """Test language validation with English."""
        serializer = UserProfileSerializer()
        result = serializer.validate_language("en")
        assert result == "en"

    def test_validate_language_japanese(self) -> None:
        """Test language validation with Japanese."""
        serializer = UserProfileSerializer()
        result = serializer.validate_language("ja")
        assert result == "ja"

    def test_validate_language_invalid_raises(self) -> None:
        """Test language validation raises error for invalid language."""
        serializer = UserProfileSerializer()
        with pytest.raises(ValidationError) as exc_info:
            serializer.validate_language("fr")
        assert "must be one of" in str(exc_info.value)


class TestWhitelistedEmailSerializer:
    """Test cases for WhitelistedEmailSerializer."""

    def test_validate_email_pattern_full_email(self) -> None:
        """Test email pattern validation with full email."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("user@example.com")
        assert result == "user@example.com"

    def test_validate_email_pattern_normalizes_to_lowercase(self) -> None:
        """Test email pattern normalizes to lowercase."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("USER@EXAMPLE.COM")
        assert result == "user@example.com"

    def test_validate_email_pattern_domain_wildcard_star(self) -> None:
        """Test email pattern with *@ domain wildcard."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("*@example.com")
        assert result == "*@example.com"

    def test_validate_email_pattern_domain_wildcard_at(self) -> None:
        """Test email pattern with @ domain wildcard."""
        serializer = WhitelistedEmailSerializer()
        result = serializer.validate_email_pattern("@example.com")
        assert result == "@example.com"

    def test_validate_email_pattern_invalid_domain_raises(self) -> None:
        """Test email pattern raises error for invalid domain."""
        serializer = WhitelistedEmailSerializer()
        with pytest.raises(ValidationError):
            serializer.validate_email_pattern("*@invalid")

    def test_validate_email_pattern_invalid_email_raises(self) -> None:
        """Test email pattern raises error for invalid email."""
        serializer = WhitelistedEmailSerializer()
        with pytest.raises(ValidationError):
            serializer.validate_email_pattern("not-an-email")


@pytest.mark.django_db
class TestPublicAccountSettingsSerializer:
    """Test cases for PublicAccountSettingsSerializer."""

    def test_serializer_fields(self) -> None:
        """Test serializer contains expected fields."""
        from apps.accounts.models import PublicAccountSettings

        settings = PublicAccountSettings.get_settings()
        serializer = PublicAccountSettingsSerializer(settings)
        data = serializer.data

        assert "registration_enabled" in data
        assert "login_enabled" in data
        assert "email_whitelist_enabled" in data

    def test_serializer_only_includes_public_fields(self) -> None:
        """Test serializer only includes public fields."""
        from apps.accounts.models import PublicAccountSettings

        settings = PublicAccountSettings.get_settings()
        serializer = PublicAccountSettingsSerializer(settings)
        data = serializer.data

        # Should only have 3 fields
        assert len(data) == 3
        # Should not include updated_at or id
        assert "updated_at" not in data
        assert "id" not in data
