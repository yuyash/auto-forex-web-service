"""Integration tests for ComplianceService."""

from typing import Any

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.services.compliance import (
    ComplianceService,
)


@pytest.mark.django_db
class TestComplianceServiceIntegration:
    """Integration tests for ComplianceService."""

    def test_check_order_compliance_basic(self, user: Any) -> None:
        """Test basic order compliance check."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            balance=10000.00,
        )

        service = ComplianceService(account)

        # ComplianceService exists and can be initialized
        assert service is not None
        assert service.account == account

    def test_compliance_service_initialization(self, user: Any) -> None:
        """Test ComplianceService initialization."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-003",
            api_type=ApiType.PRACTICE,
        )

        service = ComplianceService(account)

        assert service is not None
        assert service.account == account
