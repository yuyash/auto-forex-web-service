from __future__ import annotations

from decimal import Decimal

from apps.trading.services.floor import FloorStrategyService


def _base_config(**overrides: object) -> dict[str, object]:
    # Provide all required fields; most are irrelevant for this unit test.
    cfg: dict[str, object] = {
        "instrument": "USD_JPY",
        "base_lot_size": 1,
        "retracement_lot_mode": "additive",
        "retracement_lot_amount": 1,
        "retracement_pips": 30,
        "take_profit_pips": 9999,
        "max_layers": 1,
        "max_retracements_per_layer": 10,
        "volatility_lock_multiplier": 999,
        "retracement_trigger_progression": "equal",
        "retracement_trigger_increment": 1,
        "lot_size_progression": "equal",
        "lot_size_increment": 1,
        "entry_signal_lookback_ticks": 1,
        "momentum_lookback_source": "candles",
        "entry_signal_lookback_candles": 1,
        "entry_signal_candle_granularity_seconds": 60,
        "direction_method": "momentum",
        "sma_fast_period": 2,
        "sma_slow_period": 3,
        "ema_fast_period": 2,
        "ema_slow_period": 3,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
    }
    cfg.update(overrides)
    return cfg


def test_floor_strategy_does_not_open_multiple_retracements_at_same_price(monkeypatch):
    monkeypatch.setattr(
        "apps.trading.services.floor.get_pip_size",
        lambda *, instrument: Decimal("0.01"),
    )
    svc = FloorStrategyService(_base_config())
    state: dict[str, object] = {}

    # Tick 1 initializes and opens the initial layer at 100.00
    state, events = svc.on_tick(tick={"bid": "100.00", "ask": "100.00"}, state=state)
    assert [e["type"] for e in events].count("open") == 1

    # Tick 2 moves against by exactly 30 pips (USD_JPY pip size 0.01 => 0.30)
    state, events = svc.on_tick(tick={"bid": "99.70", "ask": "99.70"}, state=state)
    open_events = [e for e in events if e["type"] == "open"]
    assert len(open_events) == 1
    assert open_events[0]["details"]["retracement_open"] is True
    assert open_events[0]["details"]["entry_price"] == "99.70"

    # Tick 3 repeats the same mid; should NOT keep scaling in repeatedly.
    state, events = svc.on_tick(tick={"bid": "99.70", "ask": "99.70"}, state=state)
    assert [e["type"] for e in events].count("open") == 0

    # Entry price should have moved toward the retracement fill (weighted average).
    active_layers = state.get("active_layers")
    assert isinstance(active_layers, list)
    entry_price = Decimal(str(active_layers[0]["entry_price"]))
    assert entry_price == Decimal("99.85")
    assert int(active_layers[0]["retracements"]) == 1


def test_floor_strategy_close_event_includes_pnl(monkeypatch):
    monkeypatch.setattr(
        "apps.trading.services.floor.get_pip_size",
        lambda *, instrument: Decimal("0.01"),
    )
    # Make take-profit easy to hit.
    svc = FloorStrategyService(_base_config(take_profit_pips=Decimal("1")))
    state: dict[str, object] = {}

    # Tick 1 opens initial long at 100.00 (direction defaults to LONG with short history).
    state, events = svc.on_tick(
        tick={"bid": "100.00", "ask": "100.00", "timestamp": "2025-12-21T00:00:00Z"},
        state=state,
    )
    assert any(e["type"] == "open" for e in events)

    # Tick 2 moves into profit enough to trigger close.
    state, events = svc.on_tick(
        tick={"bid": "100.50", "ask": "100.50", "timestamp": "2025-12-21T00:01:00Z"},
        state=state,
    )
    close_events = [e for e in events if e["type"] == "close"]
    assert len(close_events) == 1

    details = close_events[0].get("details")
    assert isinstance(details, dict)
    assert details.get("pnl") is not None
    assert Decimal(str(details.get("pnl"))) > 0
    assert details.get("entry_time") == "2025-12-21T00:00:00Z"
    assert details.get("exit_time") == "2025-12-21T00:01:00Z"


def test_floor_strategy_re_evaluates_direction_when_opening_new_layer(monkeypatch):
    monkeypatch.setattr(
        "apps.trading.services.floor.get_pip_size",
        lambda *, instrument: Decimal("0.01"),
    )

    # Ensure the strategy can open a new layer, and that direction can flip.
    svc = FloorStrategyService(
        _base_config(
            entry_signal_lookback_ticks=2,
            max_layers=2,
            max_retracements_per_layer=1,
            retracement_pips=Decimal("1"),
            take_profit_pips=Decimal("9999"),
        )
    )
    state: dict[str, object] = {}

    # Tick 1: build history
    state, events = svc.on_tick(tick={"bid": "100.00", "ask": "100.00"}, state=state)
    assert events == []

    # Tick 2: up move -> initial layer should be long
    state, events = svc.on_tick(tick={"bid": "101.00", "ask": "101.00"}, state=state)
    open0 = [
        e for e in events if e.get("type") == "open" and e.get("details", {}).get("layer") == 0
    ]
    assert len(open0) == 1
    assert open0[0]["details"]["direction"] == "long"

    # Tick 3: big down move triggers retracement on layer 0 and unlocks layer 1.
    # History now trends down vs first element, so new layer should be short.
    state, events = svc.on_tick(tick={"bid": "99.00", "ask": "99.00"}, state=state)
    open1 = [
        e for e in events if e.get("type") == "open" and e.get("details", {}).get("layer") == 1
    ]
    assert len(open1) == 1
    assert open1[0]["details"]["direction"] == "short"

    layer_opened_1 = [
        e
        for e in events
        if e.get("type") == "layer_opened" and e.get("details", {}).get("layer") == 1
    ]
    assert len(layer_opened_1) == 1
    assert layer_opened_1[0]["details"]["direction"] == "short"


def test_floor_strategy_momentum_can_use_candle_lookback(monkeypatch):
    monkeypatch.setattr(
        "apps.trading.services.floor.get_pip_size",
        lambda *, instrument: Decimal("0.01"),
    )

    svc = FloorStrategyService(
        _base_config(
            entry_signal_lookback_ticks=1,
            momentum_lookback_source="candles",
            entry_signal_lookback_candles=3,
            entry_signal_candle_granularity_seconds=60,
        )
    )
    state: dict[str, object] = {}

    # Candle 1 close = 100.00
    state, events = svc.on_tick(
        tick={"mid": "100.00", "timestamp": "2025-12-21T00:00:10Z"},
        state=state,
    )
    # Even though tick lookback is satisfied, candle lookback is not.
    assert events == []

    # Candle 2 close = 99.00
    state, events = svc.on_tick(
        tick={"mid": "99.00", "timestamp": "2025-12-21T00:01:10Z"},
        state=state,
    )
    assert events == []

    # Candle 3 close = 98.00 => momentum is down vs candle 1 => SHORT.
    state, events = svc.on_tick(
        tick={"mid": "98.00", "timestamp": "2025-12-21T00:02:10Z"},
        state=state,
    )

    open0 = [
        e for e in events if e.get("type") == "open" and e.get("details", {}).get("layer") == 0
    ]
    assert len(open0) == 1
    assert open0[0]["details"]["direction"] == "short"
