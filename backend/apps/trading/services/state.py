"""apps.trading.services.state

State management service for task execution.

This module provides the StateManager class which handles loading, saving,
and validating execution state for task resumability.
"""

from decimal import Decimal
from typing import Any

from apps.trading.dataclasses import ExecutionState
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

        Args:
            initial_balance: Initial account balance to use if no state exists
            initial_strategy_state: Initial strategy state dict, defaults to empty dict

        Returns:
            ExecutionState: Loaded or newly initialized execution state

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
            return ExecutionState(
                strategy_state=snapshot.strategy_state,
                current_balance=snapshot.current_balance,
                open_positions=snapshot.open_positions,
                ticks_processed=snapshot.ticks_processed,
                last_tick_timestamp=snapshot.last_tick_timestamp or None,
                metrics=snapshot.metrics,
            )

        # Initialize new state
        return ExecutionState(
            strategy_state=initial_strategy_state or {},
            current_balance=initial_balance,
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics={},
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
            strategy_state=new_strategy_state,
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

        # Create and save the snapshot
        snapshot = ExecutionStateSnapshot.objects.create(
            execution=self.execution,
            sequence=sequence,
            strategy_state=state.strategy_state,
            current_balance=state.current_balance,
            open_positions=state.open_positions,
            ticks_processed=state.ticks_processed,
            last_tick_timestamp=state.last_tick_timestamp or "",
            metrics=state.metrics,
        )

        return snapshot

    def get_state(self) -> ExecutionState | None:
        """Get the current state from the most recent snapshot.

        Loads and returns the most recent state snapshot for the execution.
        Returns None if no snapshots exist.

        Returns:
            ExecutionState | None: Current state or None if no snapshots exist

        Requirements: 4.3
        """
        snapshot = (
            ExecutionStateSnapshot.objects.filter(execution=self.execution)
            .order_by("-sequence")
            .first()
        )

        if snapshot is None:
            return None

        return ExecutionState(
            strategy_state=snapshot.strategy_state,
            current_balance=snapshot.current_balance,
            open_positions=snapshot.open_positions,
            ticks_processed=snapshot.ticks_processed,
            last_tick_timestamp=snapshot.last_tick_timestamp or None,
            metrics=snapshot.metrics,
        )

    def validate_state(self, state: ExecutionState) -> tuple[bool, str | None]:
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
            tuple[bool, str | None]: (is_valid, error_message)
                is_valid: True if state is valid, False otherwise
                error_message: Error description if invalid, None if valid

        Requirements: 4.5
        """
        # Validate strategy_state is a dictionary
        if not isinstance(state.strategy_state, dict):
            return False, "strategy_state must be a dictionary"

        # Validate current_balance is non-negative
        if state.current_balance < 0:
            return False, "current_balance cannot be negative"

        # Validate open_positions is a list
        if not isinstance(state.open_positions, list):
            return False, "open_positions must be a list"

        # Validate ticks_processed is non-negative
        if state.ticks_processed < 0:
            return False, "ticks_processed cannot be negative"

        # Validate last_tick_timestamp format if present
        if state.last_tick_timestamp is not None:
            if not isinstance(state.last_tick_timestamp, str):
                return False, "last_tick_timestamp must be a string or None"

        # Validate metrics is a dictionary
        if not isinstance(state.metrics, dict):
            return False, "metrics must be a dictionary"

        return True, None

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
