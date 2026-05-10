"""Shared reconciliation protocols for stateful strategy adapters."""

from __future__ import annotations

from typing import Any, Protocol


class StrategyReconciliationState(Protocol):
    """Persisted strategy state surface used by reconciliation adapters."""

    strategy_state: dict[str, Any] | None


class AccountReconciliationState(StrategyReconciliationState, Protocol):
    """Strategy state with an account-denominated current balance."""

    current_balance: Any


class ReconciliationReportBase(Protocol):
    """Common public reconciliation report fields."""

    blockers: list[str]


class StrategyConfigLike(Protocol):
    """Persisted strategy config surface used during reconciliation."""

    config_dict: dict[str, Any]
