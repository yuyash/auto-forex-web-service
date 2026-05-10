"""Tests for drain-on-stop policy objects."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from apps.trading.services.drain import DrainCandidate, DrainPolicy
from apps.trading.utils import AccountCurrency, Money


def test_drain_candidate_keeps_pnl_currency_with_amount():
    candidate = DrainCandidate(
        position_id="pos-1",
        current_unrealized_pnl=Decimal("12.34"),
        pnl_currency="jpy",
    )

    assert candidate.current_unrealized_pnl_money == Money.coerce("12.34", "JPY")
    assert candidate.current_unrealized_pnl_money.currency == AccountCurrency("JPY")


def test_drain_policy_closes_breakeven_or_profitable_candidates():
    now = datetime(2026, 5, 10, tzinfo=UTC)
    policy = DrainPolicy(drain_started_at=now, duration_hours=0)

    decision = policy.evaluate(
        now=now,
        open_positions=[
            DrainCandidate("loss", Decimal("-0.1"), "USD"),
            DrainCandidate("flat", Decimal("0"), "USD"),
            DrainCandidate("profit", Decimal("0.01"), "USD"),
        ],
    )

    assert decision.close_position_ids == ("flat", "profit")
    assert decision.should_finalize is False


def test_drain_policy_finalizes_after_timeout():
    started = datetime(2026, 5, 10, 0, 0, tzinfo=UTC)
    policy = DrainPolicy(drain_started_at=started, duration_hours=1)

    decision = policy.evaluate(
        now=started + timedelta(hours=1),
        open_positions=[DrainCandidate("loss", Decimal("-1"), "USD")],
    )

    assert decision.should_finalize is True
    assert decision.finalize_reason == "drain_timeout"
