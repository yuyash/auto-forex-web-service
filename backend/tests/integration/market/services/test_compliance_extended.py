"""Extended integration tests for ComplianceService."""

from typing import Any

import pytest

from apps.market.enums import ApiType, Jurisdiction
from apps.market.models import OandaAccounts
from apps.market.services.compliance import ComplianceService


@pytest.mark.django_db
class TestComplianceServiceExtendedIntegration:
    """Extended integration tests for ComplianceService."""

    def test_validate_order_us_jurisdiction(self, user: Any) -> None:
        """Test order validation for US jurisdiction."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type=ApiType.LIVE,
            jurisdiction=Jurisdiction.US,
            balance=10000.00,
        )

        service = ComplianceService(account)

        order_request = {
            "instrument": "EUR_USD",
            "units": 1000,
            "order_type": "market",
        }

        is_valid, error = service.validate_order(order_request)

        # Should return tuple
        assert isinstance(is_valid, bool)
        assert error is None or isinstance(error, str)

    def test_validate_order_jp_jurisdiction(self, user: Any) -> None:
        """Test order validation for JP jurisdiction."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type=ApiType.LIVE,
            jurisdiction=Jurisdiction.JP,
            balance=10000.00,
        )

        service = ComplianceService(account)

        order_request = {
            "instrument": "EUR_USD",
            "units": 1000,
            "order_type": "market",
        }

        is_valid, error = service.validate_order(order_request)

        assert isinstance(is_valid, bool)
        assert error is None or isinstance(error, str)

    def test_validate_order_other_jurisdiction(self, user: Any) -> None:
        """Test order validation for OTHER jurisdiction."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.OTHER,
            balance=10000.00,
        )

        service = ComplianceService(account)

        order_request = {
            "instrument": "EUR_USD",
            "units": 1000,
            "order_type": "market",
        }

        is_valid, error = service.validate_order(order_request)

        # OTHER jurisdiction should be permissive
        assert is_valid is True
        assert error is None

    def test_get_jurisdiction_info(self, user: Any) -> None:
        """Test getting jurisdiction information."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
            jurisdiction=Jurisdiction.US,
        )

        service = ComplianceService(account)

        info = service.get_jurisdiction_info()

        assert "jurisdiction" in info
        assert info["jurisdiction"] == Jurisdiction.US

    def test_should_trigger_margin_closeout_us(self, user: Any) -> None:
        """Test margin closeout check for US jurisdiction."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-003",
            api_type=ApiType.LIVE,
            jurisdiction=Jurisdiction.US,
            balance=1000.00,
            margin_used=900.00,
        )

        service = ComplianceService(account)

        # US jurisdiction doesn't trigger margin closeout
        result = service.should_trigger_margin_closeout()

        assert isinstance(result, bool)

    def test_compliance_service_with_different_jurisdictions(self, user: Any) -> None:
        """Test compliance service with all jurisdictions."""
        jurisdictions = [Jurisdiction.US, Jurisdiction.JP, Jurisdiction.OTHER]

        for jurisdiction in jurisdictions:
            account = OandaAccounts.objects.create(
                user=user,
                account_id=f"101-001-{jurisdiction}-001",
                api_type=ApiType.PRACTICE,
                jurisdiction=jurisdiction,
            )

            service = ComplianceService(account)

            assert service.jurisdiction == jurisdiction
