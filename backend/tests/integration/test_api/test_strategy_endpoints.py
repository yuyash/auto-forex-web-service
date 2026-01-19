"""
Integration tests for strategy configuration API endpoints.

Tests strategy configuration CRUD operations and activation/deactivation.
"""

from django.urls import reverse

from apps.trading.models import StrategyConfigurations
from tests.integration.base import APIIntegrationTestCase
from tests.integration.factories import StrategyConfigurationFactory


class StrategyListTests(APIIntegrationTestCase):
    """Tests for strategy list endpoint."""

    def test_list_available_strategies_success(self) -> None:
        """Test listing all available trading strategies."""
        url = reverse("trading:strategy_list")

        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("strategies", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertGreater(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]

        # Verify strategy structure
        strategies = response.data["strategies"]  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(strategies, list)
        for strategy in strategies:
            self.assertIn("id", strategy)
            self.assertIn("name", strategy)
            self.assertIn("description", strategy)
            self.assertIn("config_schema", strategy)

    def test_list_strategies_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot list strategies."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("trading:strategy_list")

        response = self.client.get(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]


class StrategyDefaultsTests(APIIntegrationTestCase):
    """Tests for strategy defaults endpoint."""

    def test_get_strategy_defaults_success(self) -> None:
        """Test retrieving default parameters for a strategy."""
        url = reverse("trading:strategy_defaults", kwargs={"strategy_id": "floor"})

        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("strategy_id", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("defaults", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["strategy_id"], "floor")  # ty:ignore[possibly-missing-attribute]
        self.assertIsInstance(response.data["defaults"], dict)  # ty:ignore[possibly-missing-attribute]

    def test_get_strategy_defaults_not_found(self) -> None:
        """Test retrieving defaults for non-existent strategy returns 404."""
        url = reverse("trading:strategy_defaults", kwargs={"strategy_id": "nonexistent"})

        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_get_strategy_defaults_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot get strategy defaults."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("trading:strategy_defaults", kwargs={"strategy_id": "floor"})

        response = self.client.get(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]


class StrategyConfigListCreateTests(APIIntegrationTestCase):
    """Tests for strategy configuration list and create endpoints."""

    def test_create_strategy_config_success(self) -> None:
        """Test creating a new strategy configuration with valid data."""
        url = reverse("trading:strategy_config_list_create")
        data = {
            "name": "Test Floor Strategy",
            "strategy_type": "floor",
            "parameters": {
                "instrument": "USD_JPY",
                "base_lot_size": 1.0,
                "retracement_pips": 30.0,
                "take_profit_pips": 25.0,
                "max_layers": 3,
                "max_retracements_per_layer": 10,
            },
            "description": "Test strategy configuration",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_success(response, status_code=201)  # ty:ignore[invalid-argument-type]
        self.assertIn("id", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["name"], data["name"])  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["strategy_type"], data["strategy_type"])  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["description"], data["description"])  # ty:ignore[possibly-missing-attribute]

        # Verify config was created in database
        config = StrategyConfigurations.objects.get(id=response.data["id"])  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(config.user, self.user)
        self.assertEqual(config.name, data["name"])
        self.assertEqual(config.strategy_type, data["strategy_type"])
        self.assertEqual(config.parameters, data["parameters"])

    def test_create_strategy_config_duplicate_name(self) -> None:
        """Test that creating duplicate config name for same user fails."""
        # Create first config
        StrategyConfigurationFactory(
            user=self.user,
            name="Duplicate Name",
        )

        # Try to create duplicate
        url = reverse("trading:strategy_config_list_create")
        data = {
            "name": "Duplicate Name",
            "strategy_type": "floor",
            "parameters": {
                "instrument": "USD_JPY",
                "base_lot_size": 1.0,
                "retracement_pips": 30.0,
                "take_profit_pips": 25.0,
                "max_layers": 3,
                "max_retracements_per_layer": 10,
            },
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("name", response.data)  # ty:ignore[possibly-missing-attribute]

    def test_create_strategy_config_invalid_strategy_type(self) -> None:
        """Test that creating config with invalid strategy type fails."""
        url = reverse("trading:strategy_config_list_create")
        data = {
            "name": "Invalid Strategy",
            "strategy_type": "nonexistent_strategy",
            "parameters": {},
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("strategy_type", response.data)  # ty:ignore[possibly-missing-attribute]

    def test_create_strategy_config_missing_required_fields(self) -> None:
        """Test that creating config without required fields fails."""
        url = reverse("trading:strategy_config_list_create")
        data = {
            "strategy_type": "floor",
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_error(response, status_code=400)  # ty:ignore[invalid-argument-type]
        self.assertIn("name", response.data)  # ty:ignore[possibly-missing-attribute]

    def test_create_strategy_config_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot create configs."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("trading:strategy_config_list_create")
        data = {
            "name": "Test Strategy",
            "strategy_type": "floor",
            "parameters": {},
        }

        response = self.client.post(url, data, format="json")

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]

    def test_list_strategy_configs_success(self) -> None:
        """Test listing all strategy configs for authenticated user."""
        # Create multiple configs
        configs = StrategyConfigurationFactory.create_batch(3, user=self.user)

        url = reverse("trading:strategy_config_list_create")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("results", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["count"], 3)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["results"]), 3)  # ty:ignore[possibly-missing-attribute]

        # Verify configs are ordered by created_at descending
        result_ids = [cfg["id"] for cfg in response.data["results"]]  # ty:ignore[possibly-missing-attribute]
        expected_ids = [cfg.id for cfg in sorted(configs, key=lambda c: c.created_at, reverse=True)]
        self.assertEqual(result_ids, expected_ids)

    def test_list_strategy_configs_empty(self) -> None:
        """Test listing configs when user has no configs."""
        url = reverse("trading:strategy_config_list_create")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data["results"]), 0)  # ty:ignore[possibly-missing-attribute]

    def test_list_strategy_configs_filters_by_user(self) -> None:
        """Test that listing only returns configs belonging to the user."""
        # Create configs for current user
        StrategyConfigurationFactory.create_batch(2, user=self.user)

        # Create configs for another user
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        StrategyConfigurationFactory.create_batch(3, user=other_user)

        url = reverse("trading:strategy_config_list_create")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 2)  # ty:ignore[possibly-missing-attribute]

    def test_list_strategy_configs_filter_by_strategy_type(self) -> None:
        """Test filtering configs by strategy type."""
        # Create configs with different strategy types
        StrategyConfigurationFactory.create_batch(2, user=self.user, strategy_type="floor")
        StrategyConfigurationFactory.create_batch(
            1, user=self.user, strategy_type="floor", name="Another Floor"
        )

        url = reverse("trading:strategy_config_list_create")
        response = self.client.get(url, {"strategy_type": "floor"})

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 3)  # ty:ignore[possibly-missing-attribute]
        for config in response.data["results"]:  # ty:ignore[possibly-missing-attribute]
            self.assertEqual(config["strategy_type"], "floor")

    def test_list_strategy_configs_search(self) -> None:
        """Test searching configs by name or description."""
        # Create configs with specific names
        StrategyConfigurationFactory(
            user=self.user,
            name="Aggressive Floor Strategy",
            description="High risk strategy",
        )
        StrategyConfigurationFactory(
            user=self.user,
            name="Conservative Strategy",
            description="Low risk approach",
        )

        url = reverse("trading:strategy_config_list_create")
        response = self.client.get(url, {"search": "Aggressive"})

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 1)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("Aggressive", response.data["results"][0]["name"])  # ty:ignore[possibly-missing-attribute]

    def test_list_strategy_configs_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot list configs."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("trading:strategy_config_list_create")

        response = self.client.get(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]


class StrategyConfigDetailTests(APIIntegrationTestCase):
    """Tests for strategy configuration detail, update, and delete endpoints."""

    def test_retrieve_strategy_config_success(self) -> None:
        """Test retrieving a specific strategy configuration."""
        config = StrategyConfigurationFactory(user=self.user)
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]

        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["id"], config.id)  # ty:ignore[possibly-missing-attribute, unresolved-attribute]
        self.assertEqual(response.data["name"], config.name)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["strategy_type"], config.strategy_type)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["parameters"], config.parameters)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("is_in_use", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("created_at", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("updated_at", response.data)  # ty:ignore[possibly-missing-attribute]

    def test_retrieve_strategy_config_not_found(self) -> None:
        """Test retrieving non-existent config returns 404."""
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": 99999})

        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_retrieve_strategy_config_belongs_to_other_user(self) -> None:
        """Test that users cannot retrieve configs belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        config = StrategyConfigurationFactory(user=other_user)
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]

        response = self.client.get(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_update_strategy_config_success(self) -> None:
        """Test updating strategy config fields."""
        config = StrategyConfigurationFactory(
            user=self.user,
            name="Original Name",
            description="Original description",
        )
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]
        data = {
            "name": "Updated Name",
            "description": "Updated description",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["name"], "Updated Name")  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["description"], "Updated description")  # ty:ignore[possibly-missing-attribute]

        # Verify changes persisted in database
        config.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(config.name, "Updated Name")
        self.assertEqual(config.description, "Updated description")  # ty:ignore[unresolved-attribute]

    def test_update_strategy_config_parameters(self) -> None:
        """Test updating strategy config parameters."""
        config = StrategyConfigurationFactory(user=self.user)
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]
        new_parameters = {
            "instrument": "EUR_USD",
            "base_lot_size": 2.0,
            "retracement_pips": 40.0,
            "take_profit_pips": 30.0,
            "max_layers": 5,
            "max_retracements_per_layer": 15,
        }
        data = {
            "parameters": new_parameters,
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["parameters"], new_parameters)  # ty:ignore[possibly-missing-attribute]

        # Verify changes persisted in database
        config.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(config.parameters, new_parameters)

    def test_update_strategy_config_not_found(self) -> None:
        """Test updating non-existent config returns 404."""
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": 99999})
        data = {"name": "Updated Name"}

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_update_strategy_config_belongs_to_other_user(self) -> None:
        """Test that users cannot update configs belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        config = StrategyConfigurationFactory(user=other_user)
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]
        data = {"name": "Updated Name"}

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_delete_strategy_config_success(self) -> None:
        """Test deleting a strategy configuration."""
        config = StrategyConfigurationFactory(user=self.user)
        config_id = config.id  # ty:ignore[unresolved-attribute]
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]

        response = self.client.delete(url)

        self.assert_response_success(response, status_code=204)  # ty:ignore[invalid-argument-type]
        self.assertIn("message", response.data)  # ty:ignore[possibly-missing-attribute]

        # Verify config was deleted from database
        self.assertFalse(StrategyConfigurations.objects.filter(id=config_id).exists())

    def test_delete_strategy_config_not_found(self) -> None:
        """Test deleting non-existent config returns 404."""
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": 99999})

        response = self.client.delete(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_delete_strategy_config_belongs_to_other_user(self) -> None:
        """Test that users cannot delete configs belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        config = StrategyConfigurationFactory(user=other_user)
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]

        response = self.client.delete(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

        # Verify config still exists
        self.assertTrue(StrategyConfigurations.objects.filter(id=config.id).exists())  # ty:ignore[unresolved-attribute]


class StrategyConfigActivationTests(APIIntegrationTestCase):
    """Tests for strategy configuration activation/deactivation scenarios."""

    def test_config_is_in_use_when_active_task_exists(self) -> None:
        """Test that config shows as in use when active task exists."""
        from apps.trading.enums import TaskStatus
        from tests.integration.factories import OandaAccountFactory, TradingTaskFactory

        config = StrategyConfigurationFactory(user=self.user)
        account = OandaAccountFactory(user=self.user)

        # Create active trading task using this config
        TradingTaskFactory(
            user=self.user,
            config=config,
            oanda_account=account,
            status=TaskStatus.RUNNING,
        )

        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertTrue(response.data["is_in_use"])  # ty:ignore[possibly-missing-attribute]

    def test_config_not_in_use_when_no_active_tasks(self) -> None:
        """Test that config shows as not in use when no active tasks exist."""
        config = StrategyConfigurationFactory(user=self.user)

        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertFalse(response.data["is_in_use"])  # ty:ignore[possibly-missing-attribute]

    def test_cannot_delete_config_in_use(self) -> None:
        """Test that configs in use by active tasks cannot be deleted."""
        from apps.trading.enums import TaskStatus
        from tests.integration.factories import OandaAccountFactory, TradingTaskFactory

        config = StrategyConfigurationFactory(user=self.user)
        account = OandaAccountFactory(user=self.user)

        # Create active trading task using this config
        TradingTaskFactory(
            user=self.user,
            config=config,
            oanda_account=account,
            status=TaskStatus.RUNNING,
        )

        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]
        response = self.client.delete(url)

        self.assert_response_error(response, status_code=409)  # ty:ignore[invalid-argument-type]
        self.assertIn("error", response.data)  # ty:ignore[possibly-missing-attribute]

        # Verify config still exists
        self.assertTrue(StrategyConfigurations.objects.filter(id=config.id).exists())  # ty:ignore[unresolved-attribute]

    def test_can_update_config_parameters_when_not_in_use(self) -> None:
        """Test that config parameters can be updated when not in use."""
        config = StrategyConfigurationFactory(user=self.user)
        url = reverse("trading:strategy_config_detail", kwargs={"config_id": config.id})  # ty:ignore[unresolved-attribute]
        new_parameters = {
            "instrument": "GBP_USD",
            "base_lot_size": 3.0,
            "retracement_pips": 50.0,
            "take_profit_pips": 40.0,
            "max_layers": 4,
            "max_retracements_per_layer": 12,
        }
        data = {
            "parameters": new_parameters,
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["parameters"], new_parameters)  # ty:ignore[possibly-missing-attribute]
