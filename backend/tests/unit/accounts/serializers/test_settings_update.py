"""Unit tests for accounts serializers settings_update."""

from apps.accounts.serializers.settings_update import UserSettingsUpdateSerializer


class TestUserSettingsUpdateSerializer:
    """Test UserSettingsUpdateSerializer."""

    def test_fields_exist(self):
        serializer = UserSettingsUpdateSerializer()
        assert "timezone" in serializer.fields
        assert "language" in serializer.fields
        assert "first_name" in serializer.fields
        assert "last_name" in serializer.fields
        assert "username" in serializer.fields
        assert "notification_enabled" in serializer.fields
        assert "notification_email" in serializer.fields
        assert "notification_browser" in serializer.fields
        assert "settings_json" in serializer.fields

    def test_all_fields_optional(self):
        serializer = UserSettingsUpdateSerializer(data={})
        assert serializer.is_valid()

    def test_language_choices(self):
        serializer = UserSettingsUpdateSerializer(data={"language": "en"})
        assert serializer.is_valid()

    def test_language_invalid_choice(self):
        serializer = UserSettingsUpdateSerializer(data={"language": "fr"})
        assert not serializer.is_valid()
        assert "language" in serializer.errors
