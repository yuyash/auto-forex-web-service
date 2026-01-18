"""Unit tests for strategy registry service."""


class TestStrategyRegistry:
    """Test strategy registry."""

    def test_registry_module_exists(self):
        """Test registry module exists."""
        from apps.trading.services import registry

        assert registry is not None

    def test_registry_has_registry_instance(self):
        """Test registry module has registry instance."""
        from apps.trading.services.registry import registry

        assert registry is not None
        assert hasattr(registry, "list_strategies")

    def test_registry_can_list_strategies(self):
        """Test registry can list strategies."""
        from apps.trading.services.registry import registry

        strategies = registry.list_strategies()
        assert isinstance(strategies, list)
        assert len(strategies) > 0
