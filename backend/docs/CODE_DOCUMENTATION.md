# Trading System Code Documentation

## Overview

This document provides comprehensive documentation for the trading system codebase, including architecture overview, key components, and usage examples.

## Architecture

The trading system follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│  (Views, Serializers, WebSocket Consumers)                  │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                   Service Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Executor   │  │   Strategy   │  │    Event     │     │
│  │   Service    │  │   Registry   │  │   Service    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                   Domain Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Task        │  │  Strategy    │  │  Execution   │     │
│  │  Executor    │  │  Interface   │  │  State       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                Infrastructure Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Data        │  │  Market      │  │  Trading     │     │
│  │  Sources     │  │  Data        │  │  API         │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Executors

Executors are responsible for running trading tasks (backtests or live trading).

#### BaseExecutor

Base class for all executors with common functionality.

**Location:** `backend/apps/trading/services/executor/base.py`

**Key Methods:**

- `execute()`: Main execution loop
- `_process_tick()`: Process a single tick through the strategy
- `_handle_strategy_events()`: Handle events emitted by strategy

**Usage Example:**

```python
# Executors are typically instantiated by Celery tasks
# See BacktestExecutor and TradingExecutor for concrete implementations
```

#### BacktestExecutor

Executor for running backtests against historical data.

**Location:** `backend/apps/trading/services/executor/backtest.py`

**Key Features:**

- Loads historical ticks from configured data source
- Processes ticks in chronological order
- Simulates trading without real API calls
- Supports pause/resume/restart

**Usage Example:**

```python
from apps.trading.services.executor.backtest import BacktestExecutor
from apps.trading.services.source import RedisTickDataSource
from apps.trading.strategies.floor import FloorStrategy

# Create executor
executor = BacktestExecutor(
    execution=task_execution,
    data_source=RedisTickDataSource(redis_client),
    strategy=FloorStrategy(),
    initial_balance=Decimal("10000"),
)

# Execute backtest
executor.execute()
```

#### TradingExecutor

Executor for running live trading tasks.

**Location:** `backend/apps/trading/services/executor/trading.py`

**Key Features:**

- Subscribes to real-time market data
- Executes real trades through OANDA API
- Enforces one active task per account
- Supports pause/resume with position management

**Usage Example:**

```python
from apps.trading.services.executor.trading import TradingExecutor
from apps.trading.services.source import LiveTickDataSource
from apps.trading.strategies.floor import FloorStrategy

# Create executor
executor = TradingExecutor(
    execution=task_execution,
    data_source=LiveTickDataSource(account),
    strategy=FloorStrategy(),
    initial_balance=account.balance,
)

# Execute trading
executor.execute()
```

---

### 2. Strategies

Strategies implement trading logic as pure functions without side effects.

#### Strategy Interface

**Location:** `backend/apps/trading/strategies/base.py`

**Key Methods:**

- `on_start()`: Called when strategy starts
- `on_tick()`: Called for each market tick
- `on_stop()`: Called when strategy stops
- `on_pause()`: Called when strategy pauses
- `on_resume()`: Called when strategy resumes

**Return Type:** All methods return `tuple[TStrategyState, list[dict]]`

- First element: Updated strategy state
- Second element: List of events to emit

**Usage Example:**

```python
from apps.trading.strategies.base import Strategy
from apps.trading.dataclasses import Tick, StrategyContext

class MyStrategy(Strategy):
    def on_tick(
        self,
        tick: Tick,
        state: MyStrategyState,
        context: StrategyContext,
    ) -> tuple[MyStrategyState, list[dict]]:
        events = []

        # Make trading decision
        if self._should_buy(tick, state):
            events.append({
                "type": "signal",
                "action": "buy",
                "price": str(tick.mid),
            })

        # Update state
        new_state = state.copy_with(last_price=tick.mid)

        return new_state, events
```

#### FloorStrategy

Multi-layer retracement strategy implementation.

**Location:** `backend/apps/trading/strategies/floor/`

**Key Features:**

- Multiple entry layers with retracements
- Dynamic position sizing
- Volatility-based locking
- Take profit management

**Configuration:**

```python
{
    "initial_units": 1000,
    "max_layers": 5,
    "retracement_pips": 10,
    "take_profit_pips": 20,
    "volatility_threshold": 0.5,
}
```

---

### 3. State Management

#### StateManager

Manages execution state with persistence and validation.

**Location:** `backend/apps/trading/services/state.py`

**Key Methods:**

- `load_or_initialize()`: Load existing state or create new
- `update_strategy_state()`: Update strategy-specific state
- `save_snapshot()`: Save state snapshot for resumability
- `get_state()`: Get current state

**Usage Example:**

```python
from apps/trading.services.state import StateManager

state_manager = StateManager(execution)

# Load or initialize state
state = state_manager.load_or_initialize(
    strategy_cls=FloorStrategy,
    initial_balance=Decimal("10000"),
)

# Update state after processing tick
state_manager.update_strategy_state(new_strategy_state)

# Save snapshot periodically
state_manager.save_snapshot()
```

---

### 4. Event System

#### EventEmitter

Emits and persists events during task execution.

**Location:** `backend/apps/trading/services/events.py`

**Key Methods:**

- `emit_tick_received()`: Emit tick received event
- `emit_strategy_event()`: Emit strategy signal event
- `emit_trade_executed()`: Emit trade execution event
- `emit_status_changed()`: Emit status change event
- `emit_error()`: Emit error event

**Usage Example:**

```python
from apps.trading.services.events import EventEmitter
from apps.trading.dataclasses import EventContext

context = EventContext(
    execution=execution,
    user=user,
    account=account,
    instrument="EUR_USD",
)

emitter = EventEmitter(context)

# Emit tick received
emitter.emit_tick_received(tick)

# Emit strategy event
emitter.emit_strategy_event(
    event_type="signal",
    strategy_type="floor",
    event_data={"action": "buy", "price": "1.2345"},
)

# Emit trade executed
emitter.emit_trade_executed(trade_data)
```

---

### 5. Performance Tracking

#### PerformanceTracker

Tracks performance metrics during task execution.

**Location:** `backend/apps/trading/services/performance.py`

**Key Methods:**

- `on_tick_processed()`: Update metrics after tick processing
- `on_trade_executed()`: Update metrics after trade execution
- `update_unrealized_pnl()`: Update unrealized P&L
- `save_checkpoint()`: Save metrics checkpoint
- `get_metrics()`: Get current metrics

**Usage Example:**

```python
from apps.trading.services.performance import PerformanceTracker

tracker = PerformanceTracker(
    execution=execution,
    initial_balance=Decimal("10000"),
)

# Update after tick
tracker.on_tick_processed()

# Update after trade
tracker.on_trade_executed(trade_result)

# Save checkpoint periodically
tracker.save_checkpoint()

# Get current metrics
metrics = tracker.get_metrics()
```

---

### 6. Error Handling

#### ErrorHandler

Centralized error handling for the trading system.

**Location:** `backend/apps/trading/services/errors.py`

**Error Categories:**

- `ValidationError`: Invalid configuration or parameters
- `TransientError`: Temporary failures (network, API)
- `CriticalError`: Unrecoverable failures
- `BusinessLogicError`: Strategy or trading logic errors

**Error Actions:**

- `REJECT`: Reject the operation
- `RETRY`: Retry with exponential backoff
- `FAIL_TASK`: Fail the entire task
- `LOG_AND_CONTINUE`: Log error and continue

**Usage Example:**

```python
from apps.trading.services.errors import ErrorHandler, ErrorContext

error_handler = ErrorHandler()

try:
    # Some operation
    process_tick(tick)
except Exception as e:
    context = ErrorContext(
        execution_id=execution.id,
        task_type="backtest",
        operation="process_tick",
        tick_data=tick.to_dict(),
    )

    action = error_handler.handle_error(e, context, execution)

    if action == ErrorAction.RETRY:
        # Retry logic
        pass
    elif action == ErrorAction.FAIL_TASK:
        # Fail task
        raise
```

---

### 7. Data Sources

#### TickDataSource (Abstract)

Base interface for tick data sources.

**Location:** `backend/apps/trading/services/source.py`

**Implementations:**

- `RedisTickDataSource`: For backtests using Redis-cached data
- `LiveTickDataSource`: For live trading using real-time data

**Usage Example:**

```python
from apps.trading.services.source import RedisTickDataSource

data_source = RedisTickDataSource(redis_client)

# Get ticks for backtest
for tick in data_source.get_ticks(
    instrument="EUR_USD",
    start_time=start_dt,
    end_time=end_dt,
):
    process_tick(tick)
```

---

## Data Models

### Core Dataclasses

#### ExecutionState

Complete execution state for resumability.

**Location:** `backend/apps/trading/dataclasses/state.py`

**Fields:**

- `strategy_state`: Strategy-specific state (generic type)
- `current_balance`: Current account balance
- `open_positions`: List of open positions
- `ticks_processed`: Number of ticks processed
- `last_tick_timestamp`: Last processed tick timestamp
- `metrics`: Current performance metrics

**Usage Example:**

```python
from apps.trading.dataclasses import ExecutionState
from apps.trading.strategies.floor import FloorStrategyState

# Type-safe state access
state: ExecutionState[FloorStrategyState] = ExecutionState(
    strategy_state=FloorStrategyState(),
    current_balance=Decimal("10000"),
    open_positions=[],
    ticks_processed=0,
)

# Access strategy state with type safety
layer_count = state.strategy_state.layers  # Type-checked!
```

#### Tick

Market tick data point.

**Location:** `backend/apps/trading/dataclasses/tick.py`

**Fields:**

- `instrument`: Trading instrument
- `timestamp`: Tick timestamp (datetime)
- `bid`: Bid price (Decimal)
- `ask`: Ask price (Decimal)
- `mid`: Mid price (Decimal)

**Usage Example:**

```python
from apps.trading.dataclasses import Tick
from datetime import datetime, UTC
from decimal import Decimal

tick = Tick(
    instrument="EUR_USD",
    timestamp=datetime.now(UTC),
    bid=Decimal("1.2345"),
    ask=Decimal("1.2347"),
    mid=Decimal("1.2346"),
)
```

#### EventContext

Context for event emission.

**Location:** `backend/apps/trading/dataclasses/context.py`

**Fields:**

- `execution`: TaskExecution instance
- `user`: User instance
- `account`: OandaAccount instance (optional)
- `instrument`: Trading instrument

#### StrategyContext

Context provided to strategy methods.

**Location:** `backend/apps/trading/dataclasses/context.py`

**Fields:**

- `current_balance`: Current account balance
- `open_positions`: List of open positions
- `instrument`: Trading instrument
- `pip_size`: Pip size for instrument

---

## Database Models

### TaskExecution

Represents a single execution of a task.

**Location:** `backend/apps/trading/models/execution.py`

**Key Fields:**

- `task_type`: "backtest" or "trading"
- `task_id`: ID of the parent task
- `execution_number`: Sequential execution number
- `status`: Current execution status
- `progress`: Progress percentage (0-100)
- `started_at`: Start timestamp
- `completed_at`: Completion timestamp

**Key Methods:**

- `save_state_snapshot()`: Save state snapshot
- `load_latest_state()`: Load most recent state
- `emit_event()`: Emit an event

### ExecutionStrategyEvent

Strategy events emitted during execution.

**Location:** `backend/apps/trading/models/events.py`

**Key Fields:**

- `execution`: Foreign key to TaskExecution
- `sequence`: Sequential event number
- `event_type`: Type of event
- `strategy_type`: Strategy that emitted the event
- `timestamp`: Event timestamp
- `event`: Event data (JSON)

### ExecutionMetricsCheckpoint

Periodic metrics snapshots.

**Location:** `backend/apps/trading/models/metrics.py`

**Key Fields:**

- `execution`: Foreign key to TaskExecution
- `processed`: Number of ticks processed
- `total_return`: Total return percentage
- `total_pnl`: Total profit/loss
- `win_rate`: Win rate percentage
- `max_drawdown`: Maximum drawdown
- `sharpe_ratio`: Sharpe ratio
- `profit_factor`: Profit factor

---

## Testing

### Unit Tests

Unit tests verify individual components in isolation.

**Location:** `backend/tests/unit/trading/`

**Key Test Files:**

- `test_state_manager.py`: State management tests
- `test_event_emitter.py`: Event emission tests
- `test_performance_tracker.py`: Performance tracking tests
- `test_error_handler.py`: Error handling tests

**Example:**

```python
def test_state_manager_save_and_load():
    """Test state save and load round-trip."""
    state_manager = StateManager(execution)

    # Save state
    state = ExecutionState(...)
    state_manager.save_snapshot()

    # Load state
    loaded_state = state_manager.load_or_initialize(...)

    assert loaded_state.ticks_processed == state.ticks_processed
```

### Property-Based Tests

Property-based tests verify universal properties across many inputs.

**Framework:** Hypothesis

**Example:**

```python
from hypothesis import given
from hypothesis.strategies import decimals, integers

@given(
    balance=decimals(min_value=1000, max_value=100000),
    ticks=integers(min_value=0, max_value=10000),
)
def test_state_round_trip(balance, ticks):
    """Property: State save/load should preserve all fields."""
    state = ExecutionState(
        strategy_state={},
        current_balance=balance,
        open_positions=[],
        ticks_processed=ticks,
    )

    # Save and load
    saved = state.to_dict()
    loaded = ExecutionState.from_dict(saved)

    assert loaded.current_balance == state.current_balance
    assert loaded.ticks_processed == state.ticks_processed
```

---

## Common Patterns

### 1. Creating a New Strategy

```python
from apps.trading.strategies.base import Strategy
from dataclasses import dataclass

@dataclass
class MyStrategyState:
    """Strategy-specific state."""
    last_signal: str | None = None

    def to_dict(self):
        return {"last_signal": self.last_signal}

    @staticmethod
    def from_dict(data):
        return MyStrategyState(last_signal=data.get("last_signal"))

class MyStrategy(Strategy[MyStrategyState]):
    """My custom strategy."""

    def on_start(self, state, context):
        return state, []

    def on_tick(self, tick, state, context):
        events = []
        # Trading logic here
        return state, events

    def on_stop(self, state, context):
        return state, []
```

### 2. Running a Backtest

```python
from apps.trading.tasks.backtest import run_backtest_task

# Create backtest task
task = BacktestTask.objects.create(
    user=user,
    strategy_type="floor",
    instrument="EUR_USD",
    start_time=start_dt,
    end_time=end_dt,
    initial_balance=10000,
    config={"initial_units": 1000},
)

# Run backtest (async via Celery)
run_backtest_task.delay(task.id)
```

### 3. Monitoring Execution Progress

```python
# Get execution status
response = client.get(f"/api/trading/executions/{execution_id}/status/")
status_data = response.json()

# Get incremental events
response = client.get(
    f"/api/trading/executions/{execution_id}/events/",
    params={"since_sequence": last_sequence},
)
events = response.json()["events"]

# Get equity curve
response = client.get(f"/api/trading/executions/{execution_id}/equity/")
equity_curve = response.json()["equity_curve"]
```

---

## Best Practices

### 1. Strategy Development

- Keep strategies pure (no side effects)
- Return new state instead of mutating
- Emit events for all significant decisions
- Use Decimal for all monetary calculations
- Include comprehensive type hints

### 2. Error Handling

- Use appropriate error categories
- Include context in error messages
- Log errors with full stack traces
- Preserve state on failures
- Implement retry logic for transient errors

### 3. Performance

- Save state snapshots periodically (not every tick)
- Use batch operations for database writes
- Implement downsampling for large equity curves
- Use Redis for caching frequently accessed data

### 4. Testing

- Write unit tests for all business logic
- Use property-based tests for universal properties
- Mock external dependencies (OANDA API, Redis)
- Test error handling paths
- Verify state persistence and resumability

---

## Troubleshooting

### Common Issues

#### 1. State Not Resuming

**Symptom:** Task restarts from beginning instead of resuming

**Solution:**

- Check that state snapshots are being saved
- Verify state validation is passing
- Check for state corruption in database

#### 2. Events Not Appearing

**Symptom:** Events not showing in API or frontend

**Solution:**

- Verify EventEmitter is being used
- Check event sequence numbers are incrementing
- Verify database permissions

#### 3. Metrics Not Updating

**Symptom:** Metrics stuck at zero or not changing

**Solution:**

- Verify PerformanceTracker is being called
- Check checkpoint save frequency
- Verify trade execution is being tracked

---

## Additional Resources

- [API Documentation](./API_DOCUMENTATION.md)
- [Requirements Document](../.kiro/specs/trading-system-refactor/requirements.md)
- [Design Document](../.kiro/specs/trading-system-refactor/design.md)
- [Task List](../.kiro/specs/trading-system-refactor/tasks.md)

---

## Support

For questions or issues, please:

1. Check this documentation
2. Review the design document
3. Check existing tests for examples
4. Contact the development team
