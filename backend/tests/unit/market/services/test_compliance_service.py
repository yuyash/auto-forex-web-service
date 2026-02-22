"""Tests for apps.market.services.compliance – ComplianceService."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from apps.market.services.compliance import ComplianceService, ComplianceViolationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account(**overrides):
    account = MagicMock()
    account.jurisdiction = overrides.get("jurisdiction", ComplianceService.JURISDICTION_US)
    account.margin_available = overrides.get("margin_available", Decimal("50000"))
    account.balance = overrides.get("balance", Decimal("100000"))
    account.unrealized_pnl = overrides.get("unrealized_pnl", Decimal("0"))
    account.margin_used = overrides.get("margin_used", Decimal("0"))
    return account


# ---------------------------------------------------------------------------
# ComplianceViolationError
# ---------------------------------------------------------------------------


class TestComplianceViolationError:
    def test_is_exception(self):
        err = ComplianceViolationError("bad order")
        assert str(err) == "bad order"
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# validate_order – jurisdiction routing
# ---------------------------------------------------------------------------


class TestValidateOrderRouting:
    def test_us_jurisdiction(self):
        svc = ComplianceService(_make_account(jurisdiction="US"))
        with patch.object(svc, "_validate_us_order", return_value=(True, None)) as m:
            result = svc.validate_order({"instrument": "EUR_USD", "units": 1000})
            m.assert_called_once()
            assert result == (True, None)

    def test_jp_jurisdiction(self):
        svc = ComplianceService(_make_account(jurisdiction="JP"))
        with patch.object(svc, "_validate_jp_order", return_value=(True, None)) as m:
            svc.validate_order({"instrument": "EUR_USD", "units": 1000})
            m.assert_called_once()

    def test_eu_jurisdiction(self):
        svc = ComplianceService(_make_account(jurisdiction="EU"))
        with patch.object(svc, "_validate_eu_order", return_value=(True, None)) as m:
            svc.validate_order({"instrument": "EUR_USD", "units": 1000})
            m.assert_called_once()

    def test_uk_jurisdiction(self):
        svc = ComplianceService(_make_account(jurisdiction="UK"))
        # UK delegates to EU validation
        with patch.object(svc, "_validate_eu_order", return_value=(True, None)) as m:
            svc.validate_order({"instrument": "EUR_USD", "units": 1000})
            m.assert_called_once()

    def test_au_jurisdiction(self):
        svc = ComplianceService(_make_account(jurisdiction="AU"))
        with patch.object(svc, "_validate_au_order", return_value=(True, None)) as m:
            svc.validate_order({"instrument": "EUR_USD", "units": 1000})
            m.assert_called_once()

    def test_other_jurisdiction(self):
        svc = ComplianceService(_make_account(jurisdiction="OTHER"))
        valid, error = svc.validate_order({"instrument": "EUR_USD", "units": 1000})
        assert valid is True
        assert error is None


# ---------------------------------------------------------------------------
# _would_create_hedge
# ---------------------------------------------------------------------------


class TestWouldCreateHedge:
    @patch("apps.market.services.compliance.django_apps")
    def test_no_position_model(self, mock_apps):
        mock_apps.get_model.side_effect = LookupError("not installed")
        svc = ComplianceService(_make_account())
        assert svc._would_create_hedge("EUR_USD", 1000) is False

    @patch("apps.market.services.compliance.django_apps")
    def test_no_existing_positions(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        mock_model.objects.filter.return_value.exists.return_value = False
        svc = ComplianceService(_make_account())
        assert svc._would_create_hedge("EUR_USD", 1000) is False

    @patch("apps.market.services.compliance.django_apps")
    def test_hedge_detected(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        existing_pos = MagicMock()
        existing_pos.direction = "short"  # opposite of long (units > 0)
        qs = MagicMock()
        qs.exists.return_value = True
        qs.__iter__ = lambda self: iter([existing_pos])
        mock_model.objects.filter.return_value = qs
        svc = ComplianceService(_make_account())
        assert svc._would_create_hedge("EUR_USD", 1000) is True

    @patch("apps.market.services.compliance.django_apps")
    def test_same_direction_no_hedge(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        existing_pos = MagicMock()
        existing_pos.direction = "long"
        qs = MagicMock()
        qs.exists.return_value = True
        qs.__iter__ = lambda self: iter([existing_pos])
        mock_model.objects.filter.return_value = qs
        svc = ComplianceService(_make_account())
        assert svc._would_create_hedge("EUR_USD", 1000) is False


# ---------------------------------------------------------------------------
# should_reduce_position_instead
# ---------------------------------------------------------------------------


class TestShouldReducePositionInstead:
    def test_non_us_returns_false(self):
        svc = ComplianceService(_make_account(jurisdiction="EU"))
        result, units = svc.should_reduce_position_instead("EUR_USD", 1000)
        assert result is False
        assert units is None

    @patch("apps.market.services.compliance.django_apps")
    def test_no_hedge_returns_false(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        mock_model.objects.filter.return_value.exists.return_value = False
        svc = ComplianceService(_make_account(jurisdiction="US"))
        result, units = svc.should_reduce_position_instead("EUR_USD", 1000)
        assert result is False

    @patch("apps.market.services.compliance.django_apps")
    def test_hedge_returns_reduce_units(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model

        # _would_create_hedge needs to return True
        existing_pos = MagicMock()
        existing_pos.direction = "short"
        existing_pos.units = 500
        qs_all = MagicMock()
        qs_all.exists.return_value = True
        qs_all.__iter__ = lambda self: iter([existing_pos])

        opposite_qs = MagicMock()
        opposite_qs.__iter__ = lambda self: iter([existing_pos])

        mock_model.objects.filter.side_effect = [qs_all, opposite_qs]

        svc = ComplianceService(_make_account(jurisdiction="US"))
        result, units = svc.should_reduce_position_instead("EUR_USD", 1000)
        assert result is True
        assert units == 500


# ---------------------------------------------------------------------------
# get_fifo_position_to_close
# ---------------------------------------------------------------------------


class TestGetFifoPositionToClose:
    def test_non_us_returns_none(self):
        svc = ComplianceService(_make_account(jurisdiction="EU"))
        assert svc.get_fifo_position_to_close("EUR_USD", 1000) is None

    @patch("apps.market.services.compliance.django_apps")
    def test_no_model_returns_none(self, mock_apps):
        mock_apps.get_model.side_effect = LookupError
        svc = ComplianceService(_make_account(jurisdiction="US"))
        assert svc.get_fifo_position_to_close("EUR_USD", 1000) is None

    @patch("apps.market.services.compliance.django_apps")
    def test_returns_first_position(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        first_pos = MagicMock()
        mock_model.objects.filter.return_value.order_by.return_value.first.return_value = first_pos
        svc = ComplianceService(_make_account(jurisdiction="US"))
        assert svc.get_fifo_position_to_close("EUR_USD", 1000) is first_pos

    @patch("apps.market.services.compliance.django_apps")
    def test_no_positions_returns_none(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        mock_model.objects.filter.return_value.order_by.return_value.first.return_value = None
        svc = ComplianceService(_make_account(jurisdiction="US"))
        assert svc.get_fifo_position_to_close("EUR_USD", 1000) is None


# ---------------------------------------------------------------------------
# Leverage checks
# ---------------------------------------------------------------------------


class TestCheckUsLeverage:
    def test_major_pair_within_limit(self):
        svc = ComplianceService(_make_account(jurisdiction="US", margin_available=Decimal("50000")))
        valid, error = svc._check_us_leverage({"instrument": "EUR_USD", "units": 100000})
        # 100000 / 50 = 2000 required margin, 50000 available
        assert valid is True

    def test_major_pair_exceeds_limit(self):
        svc = ComplianceService(_make_account(jurisdiction="US", margin_available=Decimal("10")))
        valid, error = svc._check_us_leverage({"instrument": "EUR_USD", "units": 100000})
        assert valid is False
        assert "leverage" in error.lower()

    def test_minor_pair_uses_20x(self):
        svc = ComplianceService(_make_account(jurisdiction="US", margin_available=Decimal("50000")))
        # Minor pair: 100000 / 20 = 5000 required margin
        valid, error = svc._check_us_leverage({"instrument": "EUR_GBP", "units": 100000})
        assert valid is True


class TestCheckJpLeverage:
    def test_within_limit(self):
        svc = ComplianceService(_make_account(jurisdiction="JP", margin_available=Decimal("50000")))
        valid, error = svc._check_jp_leverage({"units": 100000})
        # 100000 / 25 = 4000
        assert valid is True

    def test_exceeds_limit(self):
        svc = ComplianceService(_make_account(jurisdiction="JP", margin_available=Decimal("1")))
        valid, error = svc._check_jp_leverage({"units": 100000})
        assert valid is False
        assert "Japan" in error


class TestCheckJpPositionSize:
    def test_within_limit(self):
        svc = ComplianceService(_make_account(jurisdiction="JP", balance=Decimal("100000")))
        # max = 100000 * 25 = 2500000
        valid, error = svc._check_jp_position_size({"units": 1000000})
        assert valid is True

    def test_exceeds_limit(self):
        svc = ComplianceService(_make_account(jurisdiction="JP", balance=Decimal("100")))
        # max = 100 * 25 = 2500
        valid, error = svc._check_jp_position_size({"units": 5000})
        assert valid is False
        assert "position size" in error.lower()


class TestCheckEuLeverage:
    def test_major_pair(self):
        svc = ComplianceService(_make_account(jurisdiction="EU", margin_available=Decimal("50000")))
        valid, _ = svc._check_eu_leverage({"instrument": "EUR_USD", "units": 100000})
        assert valid is True

    def test_gold_instrument(self):
        svc = ComplianceService(_make_account(jurisdiction="EU", margin_available=Decimal("50000")))
        valid, _ = svc._check_eu_leverage({"instrument": "XAU_USD", "units": 100})
        assert valid is True

    def test_crypto_instrument(self):
        svc = ComplianceService(_make_account(jurisdiction="EU", margin_available=Decimal("50000")))
        # BTC: leverage 2, so 100000 / 2 = 50000 required
        valid, _ = svc._check_eu_leverage({"instrument": "BTC_USD", "units": 100000})
        assert valid is True

    def test_crypto_exceeds(self):
        svc = ComplianceService(_make_account(jurisdiction="EU", margin_available=Decimal("10")))
        valid, error = svc._check_eu_leverage({"instrument": "BTC_USD", "units": 100000})
        assert valid is False
        assert "crypto" in error.lower()

    def test_minor_pair(self):
        svc = ComplianceService(_make_account(jurisdiction="EU", margin_available=Decimal("50000")))
        valid, _ = svc._check_eu_leverage({"instrument": "EUR_GBP", "units": 100000})
        assert valid is True


class TestCheckAuLeverage:
    def test_major_pair_within(self):
        svc = ComplianceService(_make_account(jurisdiction="AU", margin_available=Decimal("50000")))
        valid, _ = svc._check_au_leverage({"instrument": "EUR_USD", "units": 100000})
        assert valid is True

    def test_minor_pair_exceeds(self):
        svc = ComplianceService(_make_account(jurisdiction="AU", margin_available=Decimal("1")))
        valid, error = svc._check_au_leverage({"instrument": "EUR_GBP", "units": 100000})
        assert valid is False
        assert "Australia" in error


# ---------------------------------------------------------------------------
# should_trigger_margin_closeout
# ---------------------------------------------------------------------------


class TestShouldTriggerMarginCloseout:
    def test_non_eu_uk_returns_false(self):
        svc = ComplianceService(_make_account(jurisdiction="US"))
        assert svc.should_trigger_margin_closeout() is False

    def test_no_margin_used_returns_false(self):
        svc = ComplianceService(_make_account(jurisdiction="EU", margin_used=Decimal("0")))
        assert svc.should_trigger_margin_closeout() is False

    def test_margin_level_above_50_pct(self):
        svc = ComplianceService(
            _make_account(
                jurisdiction="EU",
                margin_used=Decimal("1000"),
                unrealized_pnl=Decimal("0"),
            )
        )
        # margin_level = (1000 + 0) / 1000 = 1.0 > 0.5
        assert svc.should_trigger_margin_closeout() is False

    def test_margin_level_at_50_pct(self):
        svc = ComplianceService(
            _make_account(
                jurisdiction="EU",
                margin_used=Decimal("1000"),
                unrealized_pnl=Decimal("-500"),
            )
        )
        # margin_level = (1000 + (-500)) / 1000 = 0.5 => triggers
        assert svc.should_trigger_margin_closeout() is True

    def test_margin_level_below_50_pct(self):
        svc = ComplianceService(
            _make_account(
                jurisdiction="UK",
                margin_used=Decimal("1000"),
                unrealized_pnl=Decimal("-600"),
            )
        )
        # margin_level = (1000 + (-600)) / 1000 = 0.4 < 0.5
        assert svc.should_trigger_margin_closeout() is True


# ---------------------------------------------------------------------------
# get_jurisdiction_info
# ---------------------------------------------------------------------------


class TestGetJurisdictionInfo:
    def test_us_info(self):
        svc = ComplianceService(_make_account(jurisdiction="US"))
        info = svc.get_jurisdiction_info()
        assert info["jurisdiction"] == "US"
        assert info["hedging_allowed"] is False
        assert info["fifo_required"] is True
        assert "negative_balance_protection" not in info

    def test_eu_info(self):
        svc = ComplianceService(_make_account(jurisdiction="EU"))
        info = svc.get_jurisdiction_info()
        assert info["hedging_allowed"] is True
        assert info["fifo_required"] is False
        assert info["negative_balance_protection"] is True
        assert info["margin_closeout_level"] == "50%"

    def test_uk_info(self):
        svc = ComplianceService(_make_account(jurisdiction="UK"))
        info = svc.get_jurisdiction_info()
        assert info["negative_balance_protection"] is True

    def test_other_info(self):
        svc = ComplianceService(_make_account(jurisdiction="OTHER"))
        info = svc.get_jurisdiction_info()
        assert info["hedging_allowed"] is True
        assert info["fifo_required"] is False


# ---------------------------------------------------------------------------
# _check_negative_balance (EU/UK)
# ---------------------------------------------------------------------------


class TestCheckNegativeBalance:
    def test_positive_balance(self):
        svc = ComplianceService(_make_account(balance=Decimal("1000"), unrealized_pnl=Decimal("0")))
        valid, _ = svc._check_negative_balance({})
        assert valid is True

    def test_zero_balance(self):
        svc = ComplianceService(_make_account(balance=Decimal("0"), unrealized_pnl=Decimal("0")))
        valid, error = svc._check_negative_balance({})
        assert valid is False
        assert "Negative balance" in error

    def test_negative_balance(self):
        svc = ComplianceService(
            _make_account(balance=Decimal("100"), unrealized_pnl=Decimal("-200"))
        )
        valid, error = svc._check_negative_balance({})
        assert valid is False


# ---------------------------------------------------------------------------
# Full validate_order integration-style tests
# ---------------------------------------------------------------------------


class TestValidateOrderUS:
    @patch("apps.market.services.compliance.django_apps")
    def test_hedging_rejected(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        existing_pos = MagicMock()
        existing_pos.direction = "short"
        qs = MagicMock()
        qs.exists.return_value = True
        qs.__iter__ = lambda self: iter([existing_pos])
        mock_model.objects.filter.return_value = qs

        svc = ComplianceService(_make_account(jurisdiction="US", margin_available=Decimal("50000")))
        valid, error = svc.validate_order({"instrument": "EUR_USD", "units": 1000})
        assert valid is False
        assert "Hedging" in error

    @patch("apps.market.services.compliance.django_apps")
    def test_valid_us_order(self, mock_apps):
        mock_model = MagicMock()
        mock_apps.get_model.return_value = mock_model
        mock_model.objects.filter.return_value.exists.return_value = False

        svc = ComplianceService(_make_account(jurisdiction="US", margin_available=Decimal("50000")))
        valid, error = svc.validate_order({"instrument": "EUR_USD", "units": 1000})
        assert valid is True
        assert error is None
