"""apps.trading.services.state

State management service for task execution.

This module provides the StateManager class which handles loading, saving,
and validating execution state for task resumability.
"""

from decimal import Decimal
from typing import Any

from apps.trading.dataclasses import (
    ExecutionMetrics,
    ExecutionState,
    OpenPosition,
    ValidationResult,
)
from apps.trading.models import ExecutionStateSnapshot, TaskExecution


class StateManager:
    """Manages execution state with persistence and validation.

    The StateManager is responsible for loading, saving, and validating
    execution state to enable task resumability. It uses the
    ExecutionStateSnapshot model for persistence.

    Attributes:
        execution: The TaskExecution instance this manager is associated with

    Requirements: 4.1, 4.2, 4.3, 4.5
    """

    def __init__(self, execution: TaskExecution) -> None:
        """Initialize the StateManager with a TaskExecution.

        Args:
            execution: The TaskExecution instance to manage state for
        """
        self.execution = execution

    def load_or_initialize(
        self,
        initial_balance: Decimal,
        initial_strategy_state: dict[str, Any] | None = None,
    ) -> ExecutionState:
        """Load existing state or initialize a new one.

        Attempts to load the most recent state snapshot for the execution.
        If no snapshot exists, initializes a new ExecutionState with the
        provided initial values.

        Note: The returned ExecutionState will have strategy_state as a dict.
        The caller (executor) is responsible for converting it to the appropriate
        StrategyState implementation using the strategy's from_dict method.

        Args:
            initial_balance: Initial account balance to use if no state exists
            initial_strategy_state: Initial strategy state dict, defaults to empty dict

        Returns:
            ExecutionState: Loaded or newly initialized execution state with
                           strategy_state as dict

        Requirements: 4.1, 4.3
        """
        # Try to load the most recent snapshot
        snapshot = (
            ExecutionStateSnapshot.objects.filter(execution=self.execution)
            .order_by("-sequence")
            .first()
        )

        if snapshot is not None:
            # Load state from snapshot
            # Parse positions from dict format
            positions = [
                OpenPosition.from_dict(pos_data)
                for pos_data in snapshot.open_positions
                if isinstance(pos_data, dict)
            ]

            # Parse metrics from dict format
            metrics_data = snapshot.metrics
            metrics = (
                ExecutionMetrics.from_dict(metrics_data)
                if isinstance(metrics_data, dict)
                else ExecutionMetrics()
            )

            return ExecutionState(
                strategy_state=snapshot.strategy_state,
                current_balance=snapshot.current_balance,
                open_positions=positions,
                ticks_processed=snapshot.ticks_processed,
                last_tick_timestamp=snapshot.last_tick_timestamp or None,
                metrics=metrics,
            )

        # Initialize new state
        return ExecutionState(
            strategy_state=initial_strategy_state or {},  # type: ignore[arg-type]
            current_balance=initial_balance,
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics=ExecutionMetrics(),
        )

    def update_strategy_state(
        self,
        state: ExecutionState,
        new_strategy_state: dict[str, Any],
    ) -> ExecutionState:
        """Update the strategy state within an ExecutionState.

        Creates a new ExecutionState with the updated strategy state,
        preserving all other fields. This follows an immutable pattern
        for state updates.

        Args:
            state: Current ExecutionState
            new_strategy_state: New strategy state dictionary

        Returns:
            ExecutionState: New ExecutionState with updated strategy state

        Requirements: 4.1
        """
        return ExecutionState(
            strategy_state=new_strategy_state,  # type: ignore[arg-type]
            current_balance=state.current_balance,
            open_positions=state.open_positions,
            ticks_processed=state.ticks_processed,
            last_tick_timestamp=state.last_tick_timestamp,
            metrics=state.metrics,
        )

    def save_snapshot(self, state: ExecutionState) -> ExecutionStateSnapshot:
        """Save a state snapshot to the database.

        Creates a new ExecutionStateSnapshot record with a monotonically
        increasing sequence number. This enables tracking state changes
        over time and resuming from any snapshot.

        Args:
            state: ExecutionState to save

        Returns:
            ExecutionStateSnapshot: The created snapshot record

        Requirements: 4.1, 4.2
        """
        # Get the next sequence number
        sequence = self._next_snapshot_sequence()

        # Convert strategy_state to dict if it has a to_dict method
        strategy_state_dict = state.strategy_state
        if hasattr(strategy_state_dict, "to_dict"):
            strategy_state_dict = strategy_state_dict.to_dict()
        elif not isinstance(strategy_state_dict, dict):
            # Fallback: convert to dict using __dict__ or empty dict
            strategy_state_dict = getattr(strategy_state_dict, "__dict__", {})

        # Create and save the snapshot
        snapshot = ExecutionStateSnapshot.objects.create(
            execution=self.execution,
            sequence=sequence,
            strategy_state=strategy_state_dict,
            current_balance=state.current_balance,
            open_positions=[pos.to_dict() for pos in state.open_positions],
            ticks_processed=state.ticks_processed,
            last_tick_timestamp=state.last_tick_timestamp or "",
            metrics=state.metrics.to_dict(),
        )

        return snapshot

    def get_state(self) -> ExecutionState | None:
        """Get the current state from the most recent snapshot.

        Loads and returns the most recent state snapshot for the execution.
        Returns None if no snapshots exist.

        Returns:
            ExecutionState or None: Current state or None if no snapshots exist

        Requirements: 4.3
        """
        snapshot = (
            ExecutionStateSnapshot.objects.filter(execution=self.execution)
            .order_by("-sequence")
            .first()
        )

        if snapshot is None:
            return None

        # Parse positions from dict format
        positions = [
            OpenPosition.from_dict(pos_data)
            for pos_data in snapshot.open_positions
            if isinstance(pos_data, dict)
        ]

        # Parse metrics from dict format
        metrics_data = snapshot.metrics
        metrics = (
            ExecutionMetrics.from_dict(metrics_data)
            if isinstance(metrics_data, dict)
            else ExecutionMetrics()
        )

        return ExecutionState(
            strategy_state=snapshot.strategy_state,
            current_balance=snapshot.current_balance,
            open_positions=positions,
            ticks_processed=snapshot.ticks_processed,
            last_tick_timestamp=snapshot.last_tick_timestamp or None,
            metrics=metrics,
        )

    def validate_state(self, state: ExecutionState) -> ValidationResult:
        """Validate state integrity before resuming.

        Performs validation checks on the state to ensure it's valid
        for resuming execution. Checks include:
        - Strategy state is a dictionary
        - Current balance is non-negative
        - Open positions is a list
        - Ticks processed is non-negative

        Args:
            state: ExecutionState to validate

        Returns:
            ValidationResult: Validation result with is_valid flag and optional error message

        Requirements: 4.5

        Example:
            >>> result = state_manager.validate_state(state)
            >>> if not result.is_valid:
            ...     raise ValueError(f"Invalid state: {result.error_message}")
        """
        # Validate strategy_state implements StrategyState protocol
        if not hasattr(state.strategy_state, "to_dict"):
            return ValidationResult.failure(
                "strategy_state must implement StrategyState protocol (have to_dict method)"
            )

        # Validate current_balance is non-negative
        if state.current_balance < 0:
            return ValidationResult.failure("current_balance cannot be negative")

        # Validate open_positions is a list of Position objects
        if not isinstance(state.open_positions, list):
            return ValidationResult.failure("open_positions must be a list")

        for pos in state.open_positions:
            if not isinstance(pos, OpenPosition):
                return ValidationResult.failure("open_positions must contain OpenPosition objects")

        # Validate ticks_processed is non-negative
        if state.ticks_processed < 0:
            return ValidationResult.failure("ticks_processed cannot be negative")

        # Validate last_tick_timestamp format if present
        if state.last_tick_timestamp is not None:
            if not isinstance(state.last_tick_timestamp, str):
                return ValidationResult.failure("last_tick_timestamp must be a string or None")

        # Validate metrics is an ExecutionMetrics object
        if not isinstance(state.metrics, ExecutionMetrics):
            return ValidationResult.failure("metrics must be an ExecutionMetrics object")

        return ValidationResult.success()

    def clear_state(self) -> None:
        """Clear all state snapshots for the execution.

        Deletes all ExecutionStateSnapshot records associated with the
        execution. This is useful when restarting a task from scratch.

        Requirements: 4.6
        """
        ExecutionStateSnapshot.objects.filter(execution=self.execution).delete()

    def _next_snapshot_sequence(self) -> int:
        """Get the next sequence number for a snapshot.

        Queries the database for the highest sequence number and returns
        the next value. Starts at 0 if no snapshots exist.

        Returns:
            int: Next sequence number
        """
        last_snapshot = (
            ExecutionStateSnapshot.objects.filter(execution=self.execution)
            .order_by("-sequence")
            .first()
        )

        if last_snapshot is None:
            return 0

        return last_snapshot.sequence + 1
