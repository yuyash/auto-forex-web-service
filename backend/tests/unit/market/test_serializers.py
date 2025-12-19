from __future__ import annotations

import pytest

from apps.market.serializers import OandaAccountSerializer


@pytest.mark.django_db
class TestOandaAccountSerializer:
    def test_create_sets_first_account_default(self, test_user) -> None:
        payload = {
            "account_id": "101-001-0000000-001",
            "api_token": "token-123",
            "api_type": "practice",
            "jurisdiction": "OTHER",
            "currency": "USD",
            "is_active": True,
            "is_default": False,
        }

        class _Req:
            user = test_user

        serializer = OandaAccountSerializer(data=payload, context={"request": _Req()})
        assert serializer.is_valid(), serializer.errors

        account = serializer.save()
        assert account.user_id == test_user.id
        assert account.is_default is True  # first account becomes default
        assert account.get_api_token() == "token-123"

    def test_validate_allows_duplicate_account_id_if_api_type_differs(self, test_user) -> None:
        # Create first (practice)
        payload = {
            "account_id": "101-001-0000000-002",
            "api_token": "token-abc",
            "api_type": "practice",
            "jurisdiction": "OTHER",
            "currency": "USD",
            "is_active": True,
        }

        class _Req:
            user = test_user

        serializer = OandaAccountSerializer(data=payload, context={"request": _Req()})
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        # Same account_id but different api_type should be allowed
        payload_live = {**payload, "api_type": "live", "api_token": "token-live"}
        serializer2 = OandaAccountSerializer(data=payload_live, context={"request": _Req()})
        assert serializer2.is_valid(), serializer2.errors
        serializer2.save()

        # Same account_id and same api_type should still be rejected
        serializer3 = OandaAccountSerializer(data=payload, context={"request": _Req()})
        assert serializer3.is_valid() is False
        assert "account_id" in serializer3.errors
