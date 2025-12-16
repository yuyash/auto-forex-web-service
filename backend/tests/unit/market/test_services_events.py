from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.market.enums import MarketEventType
from apps.market.services.events import MarketEventService


class TestMarketEventServiceUnit:
    def test_log_event_never_raises(self, monkeypatch) -> None:
        import apps.market.services.events as events_module

        monkeypatch.setattr(events_module.django_apps, "get_model", lambda *_args, **_kwargs: 1 / 0)

        MarketEventService().log_event(
            event_type=MarketEventType.ORDER_FAILED,
            description="x",
        )


@pytest.mark.django_db
class TestMarketEventServiceDB:
    def test_log_event_creates_record(self, test_user) -> None:
        svc = MarketEventService()
        svc.log_event(event_type=MarketEventType.ORDER_SUBMITTED, description="ok", user=test_user)

        from apps.market.models import MarketEvent

        assert MarketEvent.objects.filter(event_type=str(MarketEventType.ORDER_SUBMITTED)).exists()

    def test_log_event_ignores_unsaved_user(self) -> None:
        svc = MarketEventService()
        fake_user = MagicMock(pk=None)
        svc.log_event(event_type=MarketEventType.ORDER_SUBMITTED, description="ok", user=fake_user)

        from apps.market.models import MarketEvent

        assert MarketEvent.objects.filter(event_type=str(MarketEventType.ORDER_SUBMITTED)).exists()
