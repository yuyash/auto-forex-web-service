"""Unit tests for trading.services.reconciliation module."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.utils import timezone as dj_timezone

from apps.market.services.oanda import AccountDetails, OpenTrade, OrderDirection
from apps.trading.enums import Direction
from apps.trading.services.reconciliation import (
    ReconciliationReport,
    TradingResumeReconciler,
    _safe_decimal,
    _safe_int,
)
from apps.trading.strategies.snowball.models import (
    Entry,
    Layer,
    PositionGrid,
    Slot,
    SnowballCycle,
    SnowballStrategyState,
)

# ── Helper factories ────────────────────────────────────────────────


def _make_account_details(**overrides: Any) -> AccountDetails:
    defaults = dict(
        account_id="001",
        currency="USD",
        balance=Decimal("10000"),
        nav=Decimal("10000"),
        unrealized_pl=Decimal("0"),
        margin_used=Decimal("100"),
        margin_available=Decimal("9900"),
        position_value=Decimal("1000"),
        open_trade_count=1,
        open_position_count=1,
        pending_order_count=0,
        last_transaction_id="100",
    )
    defaults.update(overrides)
    return AccountDetails(**defaults)


def _make_open_trade(**overrides: Any) -> OpenTrade:
    defaults = dict(
        trade_id="T100",
        instrument="EUR_USD",
        direction=OrderDirection.LONG,
        units=Decimal("1000"),
        entry_price=Decimal("1.10000"),
        unrealized_pnl=Decimal("5.00"),
        open_time=dj_timezone.now(),
        state="OPEN",
        account_id="001",
    )
    defaults.update(overrides)
    return OpenTrade(**defaults)


def _make_position(**overrides: Any) -> MagicMock:
    pos = MagicMock()
    pos.id = overrides.get("id", uuid4())
    pos.oanda_trade_id = overrides.get("oanda_trade_id", "T100")
    pos.direction = overrides.get("direction", Direction.LONG)
    pos.units = overrides.get("units", 1000)
    pos.entry_price = overrides.get("entry_price", Decimal("1.10000"))
    pos.unrealized_pnl = overrides.get("unrealized_pnl", Decimal("5.00"))
    pos.entry_time = overrides.get("entry_time", dj_timezone.now())
    pos.is_open = overrides.get("is_open", True)
    pos.exit_time = overrides.get("exit_time", None)
    pos.exit_price = overrides.get("exit_price", None)
    pos.layer_index = overrides.get("layer_index", 1)
    pos.retracement_count = overrides.get("retracement_count", 0)
    return pos


def _make_reconciler(
    task: Any = None,
    state: Any = None,
) -> TradingResumeReconciler:
    if task is None:
        task = MagicMock()
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.oanda_account = MagicMock()
        task.execution_id = uuid4()
        config = MagicMock()
        config.strategy_type = "momentum"
        config.config_dict = {}
        task.config = config

    if state is None:
        state = MagicMock()
        state.strategy_state = {}
        state.current_balance = Decimal("10000")

    with patch.object(TradingResumeReconciler, "__init__", lambda self, **kw: None):
        reconciler = TradingResumeReconciler.__new__(TradingResumeReconciler)
        reconciler.task = task
        reconciler.state = state
        reconciler.execution_id = getattr(task, "execution_id", None)
        reconciler.oanda_service = MagicMock()
    return reconciler


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Eliminate retry sleep in OANDA call retry helper."""
    monkeypatch.setattr("apps.trading.services.reconciliation.time.sleep", lambda _: None)


# ── Tests for helper functions ──────────────────────────────────────


class TestSafeInt:
    def test_valid_int(self):
        assert _safe_int(42) == 42

    def test_string_int(self):
        assert _safe_int("7") == 7

    def test_none_returns_default(self):
        assert _safe_int(None) == 0
        assert _safe_int(None, 5) == 5

    def test_invalid_returns_default(self):
        assert _safe_int("abc", 99) == 99


class TestSafeDecimal:
    def test_valid_decimal(self):
        assert _safe_decimal("1.5") == Decimal("1.5")

    def test_int_input(self):
        assert _safe_decimal(10) == Decimal("10")

    def test_none_returns_default(self):
        assert _safe_decimal(None) == Decimal("0")

    def test_invalid_returns_default(self):
        assert _safe_decimal("xyz", "99") == Decimal("99")


class TestReconciliationReport:
    def test_defaults(self):
        report = ReconciliationReport()
        assert report.updated_account_snapshot is False
        assert report.broker_open_positions == 0
        assert report.pending_broker_orders == 0
        assert report.closed_local_positions == 0
        assert report.created_local_positions == 0
        assert report.updated_local_positions == 0
        assert report.removed_open_entries == 0
        assert report.synthesized_open_entries == 0
        assert report.relinked_open_entries == 0
        assert report.has_blockers is False


# ── Tests for _sync_account_snapshot ────────────────────────────────


class TestSyncAccountSnapshot:
    def test_updates_account_and_state(self):
        reconciler = _make_reconciler()
        details = _make_account_details(
            balance=Decimal("12000"),
            margin_used=Decimal("200"),
            margin_available=Decimal("11800"),
            unrealized_pl=Decimal("50"),
        )
        reconciler.oanda_service.get_account_details.return_value = details

        report = ReconciliationReport()
        reconciler._sync_account_snapshot(report)

        account = reconciler.task.oanda_account
        assert account.balance == Decimal("12000")
        assert account.margin_used == Decimal("200")
        assert account.margin_available == Decimal("11800")
        assert account.unrealized_pnl == Decimal("50")
        account.save.assert_called_once()
        assert reconciler.state.current_balance == Decimal("12000")
        assert report.updated_account_snapshot is True

    def test_raises_on_oanda_error(self):
        from apps.market.services.oanda import OandaAPIError

        reconciler = _make_reconciler()
        reconciler.oanda_service.get_account_details.side_effect = OandaAPIError("fail")

        report = ReconciliationReport()
        with pytest.raises(RuntimeError, match="Fetch account snapshot failed after"):
            reconciler._sync_account_snapshot(report)


# ── Tests for _sync_positions_with_broker ───────────────────────────


class TestSyncPositionsWithBroker:
    @patch("apps.trading.services.reconciliation.Position")
    def test_marks_missing_broker_trade_as_blocker(self, mock_pos_model):
        reconciler = _make_reconciler()
        reconciler.oanda_service.get_open_trades.return_value = []

        local_pos = _make_position(oanda_trade_id="T100")
        mock_pos_model.objects.filter.return_value.order_by.return_value = [local_pos]

        report = ReconciliationReport()
        reconciler._sync_positions_with_broker(report)

        assert report.closed_local_positions == 1
        assert report.has_blockers is True
        assert "Automatic close reconciliation is blocked" in report.blockers[0]
        local_pos.save.assert_not_called()

    @patch("apps.trading.services.reconciliation.Position")
    def test_creates_local_position_for_broker_trade(self, mock_pos_model):
        reconciler = _make_reconciler()
        broker_trade = _make_open_trade(trade_id="T200")
        reconciler.oanda_service.get_open_trades.return_value = [broker_trade]

        # No local positions
        mock_pos_model.objects.filter.return_value.order_by.return_value = []

        report = ReconciliationReport()
        reconciler._sync_positions_with_broker(report)

        assert report.created_local_positions == 1
        mock_pos_model.objects.create.assert_called_once()

    @patch("apps.trading.services.reconciliation.Position")
    def test_updates_local_position_when_units_differ(self, mock_pos_model):
        reconciler = _make_reconciler()
        broker_trade = _make_open_trade(
            trade_id="T100",
            units=Decimal("2000"),
            entry_price=Decimal("1.10000"),
            unrealized_pnl=Decimal("5.00"),
        )
        reconciler.oanda_service.get_open_trades.return_value = [broker_trade]

        local_pos = _make_position(
            oanda_trade_id="T100",
            units=1000,
            direction=Direction.LONG,
            entry_price=Decimal("1.10000"),
            unrealized_pnl=Decimal("5.00"),
        )
        mock_pos_model.objects.filter.return_value.order_by.return_value = [local_pos]

        report = ReconciliationReport()
        reconciler._sync_positions_with_broker(report)

        assert report.updated_local_positions == 1

    @patch("apps.trading.services.reconciliation.Position")
    def test_raises_on_oanda_error(self, mock_pos_model):
        from apps.market.services.oanda import OandaAPIError

        reconciler = _make_reconciler()
        reconciler.oanda_service.get_open_trades.side_effect = OandaAPIError("fail")

        report = ReconciliationReport()
        with pytest.raises(RuntimeError, match="failed after .* retries"):
            reconciler._sync_positions_with_broker(report)

    @patch("apps.trading.services.reconciliation.Position")
    def test_matched_position_no_changes(self, mock_pos_model):
        reconciler = _make_reconciler()
        broker_trade = _make_open_trade(
            trade_id="T100",
            units=Decimal("1000"),
            entry_price=Decimal("1.10000"),
            unrealized_pnl=Decimal("5.00"),
        )
        reconciler.oanda_service.get_open_trades.return_value = [broker_trade]

        local_pos = _make_position(
            oanda_trade_id="T100",
            units=1000,
            direction=Direction.LONG,
            entry_price=Decimal("1.10000"),
            unrealized_pnl=Decimal("5.00"),
        )
        mock_pos_model.objects.filter.return_value.order_by.return_value = [local_pos]

        report = ReconciliationReport()
        reconciler._sync_positions_with_broker(report)

        assert report.updated_local_positions == 0
        assert report.closed_local_positions == 0
        assert report.created_local_positions == 0

    @patch("apps.trading.services.reconciliation.Position")
    def test_short_direction_creates_negative_units(self, mock_pos_model):
        reconciler = _make_reconciler()
        broker_trade = _make_open_trade(
            trade_id="T300",
            direction=OrderDirection.SHORT,
            units=Decimal("500"),
        )
        reconciler.oanda_service.get_open_trades.return_value = [broker_trade]
        mock_pos_model.objects.filter.return_value.order_by.return_value = []

        report = ReconciliationReport()
        reconciler._sync_positions_with_broker(report)

        call_kwargs = mock_pos_model.objects.create.call_args[1]
        assert call_kwargs["direction"] == Direction.SHORT
        assert call_kwargs["units"] == -500


class TestDetectRuntimeDrift:
    @patch("apps.trading.services.reconciliation.Position")
    def test_reports_missing_broker_trade_as_runtime_drift(self, mock_pos_model):
        reconciler = _make_reconciler()
        reconciler.oanda_service.get_pending_orders.return_value = []
        reconciler.oanda_service.get_open_trades.return_value = []

        local_pos = _make_position(oanda_trade_id="T100")
        mock_pos_model.objects.filter.return_value.order_by.return_value = [local_pos]

        report = reconciler.detect_runtime_drift()

        assert report.has_blockers is True
        assert any(
            "no longer open while the trading task is running" in blocker
            for blocker in report.blockers
        )

    @patch("apps.trading.services.reconciliation.Position")
    def test_reports_extra_broker_trade_as_runtime_drift(self, mock_pos_model):
        reconciler = _make_reconciler()
        reconciler.oanda_service.get_pending_orders.return_value = []
        reconciler.oanda_service.get_open_trades.return_value = [_make_open_trade(trade_id="T200")]
        mock_pos_model.objects.filter.return_value.order_by.return_value = []

        report = reconciler.detect_runtime_drift()

        assert report.has_blockers is True
        assert any(
            "is open at the broker but is not tracked locally" in blocker
            for blocker in report.blockers
        )

    @patch("apps.trading.services.reconciliation.Position")
    def test_reports_unit_mismatch_as_runtime_drift(self, mock_pos_model):
        reconciler = _make_reconciler()
        reconciler.oanda_service.get_pending_orders.return_value = []
        reconciler.oanda_service.get_open_trades.return_value = [
            _make_open_trade(trade_id="T100", units=Decimal("2000"))
        ]

        local_pos = _make_position(oanda_trade_id="T100", units=1000)
        mock_pos_model.objects.filter.return_value.order_by.return_value = [local_pos]

        report = reconciler.detect_runtime_drift()

        assert report.has_blockers is True
        assert any(
            "units changed from local 1000 to broker 2000" in blocker for blocker in report.blockers
        )


# ── Tests for reconcile (full flow) ─────────────────────────────────


class TestReconcile:
    @patch("apps.trading.services.reconciliation.Position")
    def test_full_reconcile_non_floor_strategy(self, mock_pos_model):
        reconciler = _make_reconciler()
        reconciler.oanda_service.get_account_details.return_value = _make_account_details()
        reconciler.oanda_service.get_pending_orders.return_value = []
        reconciler.oanda_service.get_open_trades.return_value = []
        mock_pos_model.objects.filter.return_value.order_by.return_value = []

        report = reconciler.reconcile(resumed=True)

        assert isinstance(report, ReconciliationReport)
        assert report.updated_account_snapshot is True
        reconciler.state.save.assert_called_once()

    @patch("apps.trading.services.reconciliation.Position")
    def test_fresh_start_adopts_broker_open_trades_without_blocking(self, mock_pos_model):
        reconciler = _make_reconciler()
        reconciler.oanda_service.get_account_details.return_value = _make_account_details()
        reconciler.oanda_service.get_pending_orders.return_value = []
        reconciler.oanda_service.get_open_trades.return_value = [_make_open_trade()]
        mock_pos_model.objects.filter.return_value.order_by.return_value = []

        report = reconciler.reconcile(resumed=False)

        assert report.has_blockers is False
        assert report.created_local_positions == 1
        assert any(
            "Fresh start will adopt the broker exposure into the new execution" in warning
            for warning in report.warnings
        )

    @patch("apps.trading.services.reconciliation.Position")
    def test_blocks_when_pending_orders_exist(self, mock_pos_model):
        reconciler = _make_reconciler()
        reconciler.oanda_service.get_account_details.return_value = _make_account_details()
        reconciler.oanda_service.get_pending_orders.return_value = [MagicMock()]
        reconciler.oanda_service.get_open_trades.return_value = []
        mock_pos_model.objects.filter.return_value.order_by.return_value = []

        report = reconciler.reconcile(resumed=True)

        assert report.has_blockers is True
        assert "pending order" in " ".join(report.blockers).lower()


class TestSnowballReconciliation:
    def test_validate_safety_allows_snowball_position_updates(self):
        task = MagicMock()
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.oanda_account = MagicMock()
        task.execution_id = uuid4()
        config = MagicMock()
        config.strategy_type = "snowball"
        config.config_dict = {}
        task.config = config

        state = MagicMock()
        entry = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("1.10000"),
            close_price=Decimal("1.10500"),
            units=1000,
            opened_at=dj_timezone.now(),
            role="initial",
            layer_number=1,
            retracement_count=0,
        )
        cycle = SnowballCycle(
            cycle_id=1,
            direction=Direction.LONG,
            grid=PositionGrid(
                layers=[
                    Layer(
                        layer_number=1,
                        slots=[Slot(index=0, entry=entry)],
                    )
                ]
            ),
        )
        state.strategy_state = SnowballStrategyState(initialised=True, cycles=[cycle]).to_dict()

        reconciler = _make_reconciler(task=task, state=state)
        report = ReconciliationReport(
            broker_open_positions=1,
            updated_local_positions=1,
        )

        reconciler._validate_safety(report=report, resumed=True)

        assert report.has_blockers is False

    def test_validate_safety_normalizes_snowball_strategy_type(self):
        task = MagicMock()
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.oanda_account = MagicMock()
        task.execution_id = uuid4()
        config = MagicMock()
        config.strategy_type = " SnowBall "
        config.config_dict = {}
        task.config = config

        state = MagicMock()
        state.strategy_state = {"cycles": []}

        reconciler = _make_reconciler(task=task, state=state)
        report = ReconciliationReport(
            broker_open_positions=1,
            updated_local_positions=1,
        )

        reconciler._validate_safety(report=report, resumed=True)

        assert report.has_blockers is False

    def test_sync_snowball_state_relinks_position_ids(self):
        task = MagicMock()
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.oanda_account = MagicMock()
        task.execution_id = uuid4()
        config = MagicMock()
        config.strategy_type = "snowball"
        config.config_dict = {}
        task.config = config

        state = MagicMock()
        entry = Entry(
            entry_id=1,
            step=1,
            direction=Direction.LONG,
            entry_price=Decimal("1.10000"),
            close_price=Decimal("1.10500"),
            units=1000,
            opened_at=dj_timezone.now(),
            role="initial",
            layer_number=1,
            retracement_count=0,
        )
        cycle = SnowballCycle(
            cycle_id=1,
            direction=Direction.LONG,
            grid=PositionGrid(
                layers=[
                    Layer(
                        layer_number=1,
                        slots=[Slot(index=0, entry=entry)],
                    )
                ]
            ),
        )
        state.strategy_state = SnowballStrategyState(initialised=True, cycles=[cycle]).to_dict()
        state.current_balance = Decimal("10000")

        reconciler = _make_reconciler(task=task, state=state)
        position_id = uuid4()
        position = _make_position(
            id=position_id,
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("1.10010"),
            layer_index=1,
            retracement_count=0,
        )

        report = ReconciliationReport()
        reconciler._sync_strategy_state_with_positions([position], report)

        updated = SnowballStrategyState.from_strategy_state(state.strategy_state)
        synced_entry = updated.cycles[0].grid.layers[0].slots[0].entry
        assert synced_entry is not None
        assert synced_entry.position_id == str(position_id)
        assert synced_entry.entry_price == Decimal("1.10010")
        assert report.relinked_open_entries == 1
        assert report.has_blockers is False

    def test_sync_snowball_state_blocks_unmatched_open_positions(self):
        task = MagicMock()
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.oanda_account = MagicMock()
        task.execution_id = uuid4()
        config = MagicMock()
        config.strategy_type = "snowball"
        config.config_dict = {}
        task.config = config

        state = MagicMock()
        state.strategy_state = SnowballStrategyState(initialised=True, cycles=[]).to_dict()
        state.current_balance = Decimal("10000")

        reconciler = _make_reconciler(task=task, state=state)
        position = _make_position(
            id=uuid4(),
            direction=Direction.LONG,
            units=1000,
            layer_index=1,
            retracement_count=0,
        )

        report = ReconciliationReport()
        reconciler._sync_strategy_state_with_positions([position], report)

        assert report.has_blockers is True
        assert "could not match open position" in " ".join(report.blockers).lower()


# ── Tests for _match_position_for_entry ─────────────────────────────


class TestMatchPositionForEntry:
    def test_match_by_position_id(self):
        pos_id = uuid4()
        pos = _make_position(id=pos_id)
        by_id = {str(pos_id): pos}

        entry = {"position_id": str(pos_id)}
        result = TradingResumeReconciler._match_position_for_entry(
            entry=entry,
            open_positions=[pos],
            by_id=by_id,
            assigned_ids=set(),
        )
        assert result is pos

    def test_match_by_attributes_when_no_position_id(self):
        pos = _make_position(
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("1.10000"),
            layer_index=1,
        )
        by_id = {str(pos.id): pos}

        entry = {
            "floor_index": 1,
            "direction": "long",
            "units": 1000,
            "entry_price": "1.10000",
        }
        result = TradingResumeReconciler._match_position_for_entry(
            entry=entry,
            open_positions=[pos],
            by_id=by_id,
            assigned_ids=set(),
        )
        assert result is pos

    def test_returns_none_when_no_match(self):
        entry = {
            "position_id": str(uuid4()),
            "floor_index": 99,
            "direction": "long",
            "units": 9999,
            "entry_price": "2.00000",
        }
        result = TradingResumeReconciler._match_position_for_entry(
            entry=entry,
            open_positions=[],
            by_id={},
            assigned_ids=set(),
        )
        assert result is None

    def test_skips_already_assigned(self):
        pos = _make_position(direction=Direction.LONG, units=1000, layer_index=1)
        by_id = {str(pos.id): pos}

        entry = {
            "floor_index": 1,
            "direction": "long",
            "units": 1000,
            "entry_price": "1.10000",
        }
        result = TradingResumeReconciler._match_position_for_entry(
            entry=entry,
            open_positions=[pos],
            by_id=by_id,
            assigned_ids={str(pos.id)},
        )
        assert result is None

    def test_picks_closest_price(self):
        pos1 = _make_position(
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("1.10000"),
            layer_index=1,
        )
        pos2 = _make_position(
            direction=Direction.LONG,
            units=1000,
            entry_price=Decimal("1.10500"),
            layer_index=1,
        )
        by_id = {str(pos1.id): pos1, str(pos2.id): pos2}

        entry = {
            "floor_index": 1,
            "direction": "long",
            "units": 1000,
            "entry_price": "1.10400",
        }
        result = TradingResumeReconciler._match_position_for_entry(
            entry=entry,
            open_positions=[pos1, pos2],
            by_id=by_id,
            assigned_ids=set(),
        )
        assert result is pos2
