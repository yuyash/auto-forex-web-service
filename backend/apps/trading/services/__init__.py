"""Service layer for the trading app."""

from .registry import register_all_strategies, registry

__all__ = ["registry", "register_all_strategies"]
