"""Pytest fixtures for end-to-end tests.

These tests run against real PostgreSQL and Redis.
OANDA API access uses a real practice account via GitHub Secrets.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfiguration
from tests.e2e.helpers import (
    E2E_PASSWORD,
    OANDA_ACCOUNT_ID,
    OANDA_API_TOKEN,
    CsvTickDataSource,
)

# Register the API report plugin
pytest_plugins = ["tests.e2e.plugin_api_report"]

User = get_user_model()

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TICK_CSV = FIXTURES_DIR / "tick_data_usd_jpy.csv"


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Create tables and load tick data fixture once per session."""
    with django_db_blocker.unblock():
        call_command("migrate", "--run-syncdb", verbosity=0)
        if TICK_CSV.exists():
            call_command("load_data", from_csv=str(TICK_CSV))


@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user with a known password."""
    user = User.objects.create_user(
        username="e2e_testuser",
        email="e2e_test@example.com",
        password=E2E_PASSWORD,
    )
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return user


@pytest.fixture
def auth_tokens(api_client, test_user):
    """Login and return (access_token, refresh_token) tuple."""
    resp = api_client.post(
        "/api/accounts/auth/login",
        {"email": test_user.email, "password": E2E_PASSWORD},
        format="json",
    )
    assert resp.status_code == 200, resp.data
    return resp.data["token"], resp.data["refresh_token"]


@pytest.fixture
def authenticated_client(api_client, auth_tokens):
    """API client with JWT Authorization header."""
    token, _ = auth_tokens
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def oanda_account(test_user, db):
    """Create an OANDA practice account."""
    account = OandaAccounts.objects.create(
        user=test_user,
        account_id=OANDA_ACCOUNT_ID or "101-001-00000000-001",
        api_type="practice",
        is_active=True,
    )
    account.set_api_token(OANDA_API_TOKEN or "dummy-token-for-ci")
    account.save()
    return account


@pytest.fixture
def strategy_config(test_user, db):
    """Create a floor strategy configuration for USD_JPY."""
    return StrategyConfiguration.objects.create(
        user=test_user,
        name="E2E Floor Strategy",
        strategy_type="floor",
        parameters={
            "instrument": "USD_JPY",
            "base_lot_size": 1.0,
            "retracement_pips": 30.0,
            "take_profit_pips": 25.0,
            "max_layers": 3,
            "max_retracements_per_layer": 10,
        },
    )


@pytest.fixture
def csv_tick_data_source():
    """CsvTickDataSource pointing to the fixture CSV."""
    return CsvTickDataSource(TICK_CSV, batch_size=200)


@pytest.fixture
def executed_backtest_task_id(authenticated_client, strategy_config):
    """Create, start, and wait for a backtest task to complete.

    Returns the task_id of the completed backtest.
    Celery runs in eager mode so the task executes synchronously.
    """
    # Create
    resp = authenticated_client.post(
        "/api/trading/tasks/backtest/",
        {
            "name": "Fixture Executed Backtest",
            "config": str(strategy_config.id),
            "instrument": "USD_JPY",
            "start_time": "2026-01-02T00:00:00Z",
            "end_time": "2026-01-02T21:59:58Z",
            "initial_balance": "10000.00",
            "data_source": "postgresql",
        },
        format="json",
    )
    assert resp.status_code in (200, 201), resp.data

    # Retrieve task_id from list
    list_resp = authenticated_client.get(
        "/api/trading/tasks/backtest/", {"search": "Fixture Executed Backtest"}
    )
    assert list_resp.status_code == 200
    results = list_resp.data.get("results", list_resp.data)
    task = next(t for t in results if t["name"] == "Fixture Executed Backtest")
    task_id = task["id"]

    # Start (runs synchronously in eager mode)
    start_resp = authenticated_client.post(f"/api/trading/tasks/backtest/{task_id}/start/")
    assert start_resp.status_code == 200, start_resp.data

    return task_id


@pytest.fixture
def executed_trading_task_id(authenticated_client, oanda_account, strategy_config):
    """Create, start, and wait for a dry-run trading task to complete.

    Patches LiveTickDataSource with CsvTickDataSource so the task
    reads from the fixture CSV instead of a live OANDA stream.
    Returns the task_id of the completed trading task.
    """
    # Create
    resp = authenticated_client.post(
        "/api/trading/tasks/trading/",
        {
            "name": "Fixture Executed Trading",
            "config_id": str(strategy_config.id),
            "account_id": oanda_account.id,
            "dry_run": True,
        },
        format="json",
    )
    assert resp.status_code in (200, 201), resp.data

    # Retrieve task_id from list
    list_resp = authenticated_client.get(
        "/api/trading/tasks/trading/", {"search": "Fixture Executed Trading"}
    )
    assert list_resp.status_code == 200
    results = list_resp.data.get("results", list_resp.data)
    task = next(t for t in results if t["name"] == "Fixture Executed Trading")
    task_id = task["id"]

    # Start with patched data source
    csv_source = CsvTickDataSource(TICK_CSV, batch_size=200)
    with patch(
        "apps.trading.tasks.trading.LiveTickDataSource",
        return_value=csv_source,
    ):
        start_resp = authenticated_client.post(f"/api/trading/tasks/trading/{task_id}/start/")
        assert start_resp.status_code == 200, start_resp.data

    return task_id
