"""Service layer for the trading app."""

from .registry import registry, register_all_strategies

__all__ = ["registry", "register_all_strategies"]
