from __future__ import annotations

from decimal import Decimal

import pytest

from apps.market.models import OandaAccount
from apps.market.services.compliance import ComplianceService


@pytest.mark.django_db
class TestComplianceService:
    def test_us_violates_leverage_when_margin_insufficient(self, test_user) -> None:
        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-010",
            api_token="encrypted",
            api_type="practice",
            jurisdiction="US",
            currency="USD",
            margin_available=Decimal("1.00"),
            is_active=True,
        )

        svc = ComplianceService(account)
        ok, err = svc.validate_order({"instrument": "EUR_USD", "units": 100000})
        assert ok is False
        assert err is not None

    def test_other_jurisdiction_allows(self, test_user) -> None:
        account = OandaAccount.objects.create(
            user=test_user,
            account_id="101-001-0000000-011",
            api_token="encrypted",
            api_type="practice",
            jurisdiction="OTHER",
            currency="USD",
            margin_available=Decimal("0"),
            is_active=True,
        )

        svc = ComplianceService(account)
        ok, err = svc.validate_order({"instrument": "EUR_USD", "units": 1})
        assert ok is True
        assert err is None
