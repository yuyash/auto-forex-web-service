"""Integration tests for market enums."""

import pytest

from apps.market.enums import ApiType, Jurisdiction


@pytest.mark.django_db
class TestEnumsIntegration:
    """Integration tests for market enums."""

    def test_api_type_in_model_choices(self) -> None:
        """Test that ApiType values work with Django model choices."""
        from apps.market.models import OandaAccounts

        # Get choices from model field
        field = OandaAccounts._meta.get_field("api_type")
        if field.choices:
            choice_values = [choice[0] for choice in field.choices]

            # Verify all ApiType values are in choices
            assert ApiType.PRACTICE in choice_values
            assert ApiType.LIVE in choice_values

    def test_jurisdiction_in_model_choices(self) -> None:
        """Test that Jurisdiction values work with Django model choices."""
        from apps.market.models import OandaAccounts

        # Get choices from model field
        field = OandaAccounts._meta.get_field("jurisdiction")
        if field.choices:
            choice_values = [choice[0] for choice in field.choices]

            # Verify Jurisdiction values are in choices
            assert Jurisdiction.US in choice_values
            assert Jurisdiction.JP in choice_values
            assert Jurisdiction.OTHER in choice_values
