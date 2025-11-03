"""
Serializers for user authentication and management.

This module contains serializers for:
- User registration
- User login
- User profile
"""

import re
from typing import TYPE_CHECKING, Any, Dict

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

if TYPE_CHECKING:
    from accounts.models import SystemSettings as SystemSettingsType
    from accounts.models import User as UserType
else:
    from accounts.models import SystemSettings as SystemSettingsType

    UserType = get_user_model()

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.

    Requirements: 1.1, 1.2, 1.3, 1.5
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="Password must be at least 8 characters long",
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="Confirm password",
    )

    class Meta:
        model = User
        fields = ["email", "username", "password", "password_confirm"]
        extra_kwargs = {
            "email": {"required": True},
            "username": {"required": False},
        }

    def validate_email(self, value: str) -> str:
        """
        Validate email format and uniqueness.

        Args:
            value: Email address to validate

        Returns:
            Validated email address

        Raises:
            serializers.ValidationError: If email is invalid or already exists
        """
        # Validate email format
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, value):
            raise serializers.ValidationError("Enter a valid email address.")

        # Normalize email to lowercase for case-insensitive comparison
        normalized_email = value.lower()

        # Check email uniqueness (case-insensitive)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("A user with this email address already exists.")

        return normalized_email

    def validate_password(self, value: str) -> str:
        """
        Validate password strength using Django's password validators.

        Args:
            value: Password to validate

        Returns:
            Validated password

        Raises:
            serializers.ValidationError: If password doesn't meet requirements
        """
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))

        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that passwords match.

        Args:
            attrs: Dictionary of field values

        Returns:
            Validated attributes

        Raises:
            serializers.ValidationError: If passwords don't match
        """
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> "UserType":
        """
        Create a new user with hashed password.

        Args:
            validated_data: Validated user data

        Returns:
            Created user instance
        """
        # Remove password_confirm as it's not needed for user creation
        validated_data.pop("password_confirm")

        # Generate username from email if not provided
        if "username" not in validated_data or not validated_data["username"]:
            email = validated_data["email"]
            base_username = email.split("@")[0]
            username = base_username

            # Ensure username is unique
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            validated_data["username"] = username

        # Create user with hashed password
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )

        return user


class UserLoginSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    Serializer for user login.

    Requirements: 2.1, 2.2, 2.3

    Note: This is a read-only serializer used only for validation.
    It does not implement create() or update() methods as it never persists data.
    """

    email = serializers.EmailField(required=True, help_text="User's email address")
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
        help_text="User's password",
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate login credentials.

        Args:
            attrs: Dictionary of field values

        Returns:
            Validated attributes with user instance

        Raises:
            serializers.ValidationError: If credentials are invalid
        """
        email = attrs.get("email", "").lower()
        password = attrs.get("password", "")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        # Authenticate user
        user = authenticate(username=email, password=password)

        if user is None:
            # Don't reveal whether email or password is incorrect
            raise serializers.ValidationError("Invalid credentials.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        if user.is_locked:
            raise serializers.ValidationError(
                "Account is locked due to excessive failed login attempts. Please contact support."
            )

        attrs["user"] = user
        return attrs


class SystemSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for system settings.

    Requirements: 1.1, 2.1, 19.5, 28.5
    """

    class Meta:
        model = SystemSettingsType
        fields = ["registration_enabled", "login_enabled", "updated_at"]
        read_only_fields = ["updated_at"]


class PublicSystemSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for public system settings (no auth required).

    Only exposes the enabled flags without sensitive information.

    Requirements: 1.1, 2.1
    """

    class Meta:
        model = SystemSettingsType
        fields = ["registration_enabled", "login_enabled"]


class UserSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for user settings.

    Requirements: 29.1, 29.2, 29.3, 29.4, 30.1, 30.2, 30.4, 31.1, 31.2, 31.4
    """

    class Meta:
        from accounts.models import UserSettings  # pylint: disable=import-outside-toplevel

        model = UserSettings
        fields = [
            "default_lot_size",
            "default_scaling_mode",
            "default_retracement_pips",
            "default_take_profit_pips",
            "notification_enabled",
            "notification_email",
            "notification_browser",
            "settings_json",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_default_lot_size(self, value: float) -> float:
        """
        Validate default lot size is positive.

        Args:
            value: Lot size to validate

        Returns:
            Validated lot size

        Raises:
            serializers.ValidationError: If lot size is invalid
        """
        if value <= 0:
            raise serializers.ValidationError("Lot size must be greater than 0.")
        if value > 1000000:
            raise serializers.ValidationError("Lot size must not exceed 1,000,000.")
        return value

    def validate_default_scaling_mode(self, value: str) -> str:
        """
        Validate scaling mode is valid.

        Args:
            value: Scaling mode to validate

        Returns:
            Validated scaling mode

        Raises:
            serializers.ValidationError: If scaling mode is invalid
        """
        valid_modes = ["additive", "multiplicative"]
        if value not in valid_modes:
            raise serializers.ValidationError(
                f"Scaling mode must be one of: {', '.join(valid_modes)}"
            )
        return value

    def validate_default_retracement_pips(self, value: int) -> int:
        """
        Validate retracement pips is within valid range.

        Args:
            value: Retracement pips to validate

        Returns:
            Validated retracement pips

        Raises:
            serializers.ValidationError: If retracement pips is invalid
        """
        if value < 1:
            raise serializers.ValidationError("Retracement pips must be at least 1.")
        if value > 1000:
            raise serializers.ValidationError("Retracement pips must not exceed 1000.")
        return value

    def validate_default_take_profit_pips(self, value: int) -> int:
        """
        Validate take profit pips is within valid range.

        Args:
            value: Take profit pips to validate

        Returns:
            Validated take profit pips

        Raises:
            serializers.ValidationError: If take profit pips is invalid
        """
        if value < 1:
            raise serializers.ValidationError("Take profit pips must be at least 1.")
        if value > 1000:
            raise serializers.ValidationError("Take profit pips must not exceed 1000.")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile including timezone and language preferences.

    Requirements: 29.1, 29.2, 30.1, 30.2, 30.4, 31.1, 31.2, 31.4
    """

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "timezone",
            "language",
            "is_staff",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "email", "username", "is_staff", "created_at", "updated_at"]

    def validate_timezone(self, value: str) -> str:
        """
        Validate timezone is a valid IANA timezone identifier.

        Args:
            value: Timezone to validate

        Returns:
            Validated timezone

        Raises:
            serializers.ValidationError: If timezone is invalid
        """
        import zoneinfo  # pylint: disable=import-outside-toplevel

        try:
            zoneinfo.ZoneInfo(value)
        except zoneinfo.ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                f"'{value}' is not a valid IANA timezone identifier."
            ) from exc
        return value

    def validate_language(self, value: str) -> str:
        """
        Validate language is supported.

        Args:
            value: Language code to validate

        Returns:
            Validated language code

        Raises:
            serializers.ValidationError: If language is not supported
        """
        valid_languages = ["en", "ja"]
        if value not in valid_languages:
            raise serializers.ValidationError(
                f"Language must be one of: {', '.join(valid_languages)}"
            )
        return value


class OandaAccountSerializer(serializers.ModelSerializer):
    """
    Serializer for OANDA account.

    Requirements: 4.1, 4.5
    """

    api_token = serializers.CharField(
        write_only=True,
        required=True,
        help_text="OANDA API token (will be encrypted)",
    )

    class Meta:
        from accounts.models import OandaAccount  # pylint: disable=import-outside-toplevel

        model = OandaAccount
        fields = [
            "id",
            "account_id",
            "api_token",
            "api_type",
            "jurisdiction",
            "currency",
            "balance",
            "margin_used",
            "margin_available",
            "unrealized_pnl",
            "is_active",
            "status",
            "enable_position_differentiation",
            "position_diff_increment",
            "position_diff_pattern",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "balance",
            "margin_used",
            "margin_available",
            "unrealized_pnl",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate_account_id(self, value: str) -> str:
        """
        Validate account_id format and uniqueness for the user.

        Args:
            value: Account ID to validate

        Returns:
            Validated account ID

        Raises:
            serializers.ValidationError: If account_id is invalid or already exists
        """
        from accounts.models import OandaAccount  # pylint: disable=import-outside-toplevel

        # Check if this is an update operation
        if self.instance:
            # For updates, allow the same account_id if it's the same instance
            user = self.instance.user
            if self.instance.account_id == value:
                return value
        else:
            # For create operations, get user from context
            request = self.context.get("request")
            user = request.user if request and hasattr(request, "user") else None

        # Check uniqueness for authenticated user
        if (
            user
            and hasattr(user, "is_authenticated")
            and user.is_authenticated
            and OandaAccount.objects.filter(user=user, account_id=value).exists()
        ):
            raise serializers.ValidationError("You already have an account with this account ID.")

        return value

    def validate_api_type(self, value: str) -> str:
        """
        Validate api_type is either 'practice' or 'live'.

        Args:
            value: API type to validate

        Returns:
            Validated API type

        Raises:
            serializers.ValidationError: If api_type is invalid
        """
        if value not in ["practice", "live"]:
            raise serializers.ValidationError("API type must be either 'practice' or 'live'.")

        return value

    def validate_jurisdiction(self, value: str) -> str:
        """
        Validate jurisdiction is a valid choice.

        Args:
            value: Jurisdiction to validate

        Returns:
            Validated jurisdiction

        Raises:
            serializers.ValidationError: If jurisdiction is invalid
        """
        valid_jurisdictions = ["US", "JP", "EU", "UK", "AU", "OTHER"]
        if value not in valid_jurisdictions:
            raise serializers.ValidationError(
                f"Jurisdiction must be one of: {', '.join(valid_jurisdictions)}"
            )

        return value

    def validate_position_diff_increment(self, value: int) -> int:
        """
        Validate position differentiation increment is within allowed range.

        Args:
            value: Increment amount to validate

        Returns:
            Validated increment amount

        Raises:
            serializers.ValidationError: If increment is out of range
        """
        if value < 1 or value > 100:
            raise serializers.ValidationError("Increment amount must be between 1 and 100 units.")

        return value

    def validate_position_diff_pattern(self, value: str) -> str:
        """
        Validate position differentiation pattern is a valid choice.

        Args:
            value: Pattern to validate

        Returns:
            Validated pattern

        Raises:
            serializers.ValidationError: If pattern is invalid
        """
        valid_patterns = ["increment", "decrement", "alternating"]
        if value not in valid_patterns:
            raise serializers.ValidationError(
                f"Pattern must be one of: {', '.join(valid_patterns)}"
            )

        return value

    def create(self, validated_data: Dict[str, Any]) -> Any:
        """
        Create a new OANDA account with encrypted API token.

        Args:
            validated_data: Validated account data

        Returns:
            Created OandaAccount instance
        """
        from accounts.models import OandaAccount  # pylint: disable=import-outside-toplevel

        # Extract api_token before creating the account
        api_token = validated_data.pop("api_token")

        # Get user from request context
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            raise serializers.ValidationError("User context is required")

        user = request.user

        # Create account
        account = OandaAccount.objects.create(user=user, **validated_data)

        # Set encrypted API token
        account.set_api_token(api_token)
        account.save()

        return account

    def update(self, instance: Any, validated_data: Dict[str, Any]) -> Any:
        """
        Update an existing OANDA account.

        Args:
            instance: Existing OandaAccount instance
            validated_data: Validated account data

        Returns:
            Updated OandaAccount instance
        """
        # Extract api_token if provided
        api_token = validated_data.pop("api_token", None)

        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update API token if provided
        if api_token:
            instance.set_api_token(api_token)

        instance.save()
        return instance


class TimezoneAwareDateTimeField(serializers.DateTimeField):
    """
    Custom DateTimeField that converts timestamps to user's timezone.

    This field automatically converts datetime values to the user's preferred
    timezone when serializing (output) and converts from user's timezone to UTC
    when deserializing (input).

    Requirements: 30.1, 30.2, 30.3, 30.5
    """

    def to_representation(self, value: Any) -> Any:
        """
        Convert datetime to user's timezone for output.

        Args:
            value: Datetime value to convert

        Returns:
            ISO 8601 formatted datetime string in user's timezone
        """
        from accounts.timezone_utils import (  # pylint: disable=import-outside-toplevel
            convert_to_user_timezone,
        )

        if value is None:
            return None

        # Get user from context
        request = self.context.get("request")
        user_timezone = None

        if request and hasattr(request, "user") and request.user.is_authenticated:
            user_timezone = request.user.timezone

        # Convert to user's timezone (defaults to UTC if not specified)
        converted_value = convert_to_user_timezone(value, user_timezone)

        # Use parent's to_representation to format as ISO 8601
        return super().to_representation(converted_value)

    def to_internal_value(self, value: Any) -> Any:
        """
        Convert datetime from user's timezone to UTC for storage.

        Args:
            value: Datetime value to convert

        Returns:
            Datetime in UTC
        """
        from accounts.timezone_utils import (  # pylint: disable=import-outside-toplevel
            convert_from_user_timezone,
        )

        # Use parent's to_internal_value to parse the datetime
        dt = super().to_internal_value(value)

        # Get user from context
        request = self.context.get("request")
        user_timezone = None

        if request and hasattr(request, "user") and request.user.is_authenticated:
            user_timezone = request.user.timezone

        # Convert from user's timezone to UTC
        return convert_from_user_timezone(dt, user_timezone)
