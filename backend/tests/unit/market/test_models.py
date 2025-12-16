from __future__ import annotations

from decimal import Decimal

import pytest

from apps.market.models import CeleryTaskStatus, TickData


@pytest.mark.django_db
class TestMarketModels:
    def test_celery_task_status_str(self) -> None:
        row = CeleryTaskStatus.objects.create(task_name="t", instance_key="k")
        assert "t" in str(row)
        assert "k" in str(row)

    def test_tickdata_spread_property(self) -> None:
        tick = TickData(
            instrument="EUR_USD",
            timestamp="2025-01-01T00:00:00Z",
            bid=Decimal("1.10000"),
            ask=Decimal("1.10010"),
            mid=Decimal("1.10005"),
        )
        assert tick.spread == Decimal("0.00010")
