"""
Test data factories for integration tests.

This module provides Factory Boy factories for creating realistic test data
for integration tests. Factories use Faker to generate random but realistic
data values.
"""

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory
from faker import Faker

from apps.accounts.models import UserNotification
from apps.market.enums import ApiType, Jurisdiction
from apps.market.models import OandaAccounts, TickData
from apps.trading.models import (
    BacktestTask,
    StrategyConfiguration,
    TradingTask,
)

User = get_user_model()
fake = Faker()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.Sequence(lambda n: f"testuser{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    is_active = True
    email_verified = True
    timezone = "UTC"
    language = "en"
    is_locked = False
    failed_login_attempts = 0


class OandaAccountFactory(DjangoModelFactory):
    """Factory for creating test OANDA accounts."""

    class Meta:
        model = OandaAccounts

    user = factory.SubFactory(UserFactory)
    account_id = factory.Sequence(lambda n: f"101-{n:03d}-{fake.random_int(100000, 999999)}")
    api_type = ApiType.PRACTICE
    jurisdiction = Jurisdiction.OTHER
    currency = "USD"
    balance = factory.Faker(
        "pydecimal",
        left_digits=6,
        right_digits=2,
        positive=True,
        min_value=1000.01,
        max_value=100000,
    )
    margin_used = factory.Faker(
        "pydecimal", left_digits=5, right_digits=2, positive=True, min_value=0.01, max_value=10000
    )
    margin_available = factory.LazyAttribute(lambda obj: obj.balance - obj.margin_used)
    unrealized_pnl = factory.Faker(
        "pydecimal", left_digits=4, right_digits=2, min_value=-1000, max_value=1000
    )
    is_active = True
    is_default = False
    is_used = False

    @factory.post_generation
    def set_encrypted_token(obj, create, extracted, **kwargs):  # type: ignore[no-untyped-def]
        """Set encrypted API token after creation."""
        if not create:
            return

        token = extracted if extracted else fake.sha256()
        obj.set_api_token(token)  # type: ignore[attr-defined]
        obj.save()  # type: ignore[attr-defined]


class TickDataFactory(DjangoModelFactory):
    """Factory for creating test tick data."""

    class Meta:
        model = TickData

    instrument = factory.Faker(
        "random_element", elements=["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD"]
    )
    timestamp = factory.Faker("date_time_this_month", tzinfo=None)
    bid = factory.Faker(
        "pydecimal", left_digits=1, right_digits=5, positive=True, min_value=1.0, max_value=2.0
    )
    ask = factory.LazyAttribute(
        lambda obj: obj.bid
        + fake.pydecimal(
            left_digits=0, right_digits=5, positive=True, min_value=0.00001, max_value=0.0001
        )
    )
    mid = factory.LazyAttribute(lambda obj: (obj.bid + obj.ask) / 2)


class StrategyConfigurationFactory(DjangoModelFactory):
    """Factory for creating test strategy configurations."""

    class Meta:
        model = StrategyConfiguration

    user = factory.SubFactory(UserFactory)
    name = factory.Faker("catch_phrase")
    strategy_type = "floor"
    parameters = factory.LazyFunction(
        lambda: {
            "instrument": "USD_JPY",
            "base_lot_size": 1.0,
            "retracement_pips": 30.0,
            "take_profit_pips": 25.0,
            "max_layers": 3,
            "max_retracements_per_layer": 10,
        }
    )


class BacktestTaskFactory(DjangoModelFactory):
    """Factory for creating test backtest tasks."""

    class Meta:
        model = BacktestTask

    user = factory.SubFactory(UserFactory)
    name = factory.Faker("catch_phrase")
    config = factory.SubFactory(StrategyConfigurationFactory)
    instrument = "USD_JPY"
    start_time = factory.Faker("date_time_this_year", tzinfo=None)
    end_time = factory.LazyAttribute(
        lambda obj: fake.date_time_between(start_date=obj.start_time, end_date="+30d", tzinfo=None)
    )
    initial_balance = factory.Faker(
        "pydecimal", left_digits=6, right_digits=2, positive=True, min_value=10000, max_value=100000
    )
    status = "pending"
    data_source = "postgresql"


class TradingTaskFactory(DjangoModelFactory):
    """Factory for creating test trading tasks."""

    class Meta:
        model = TradingTask

    user = factory.SubFactory(UserFactory)
    oanda_account = factory.SubFactory(OandaAccountFactory)
    config = factory.SubFactory(StrategyConfigurationFactory)
    name = factory.Faker("catch_phrase")
    instrument = "USD_JPY"
    status = "created"


class UserNotificationFactory(DjangoModelFactory):
    """Factory for creating test user notifications."""

    class Meta:
        model = UserNotification

    user = factory.SubFactory(UserFactory)
    notification_type = factory.Faker(
        "random_element",
        elements=["trade_closed", "account_alert", "risk_limit_breach", "system_notification"],
    )
    title = factory.Faker("sentence", nb_words=5)
    message = factory.Faker("paragraph", nb_sentences=3)
    severity = factory.Faker("random_element", elements=["info", "warning", "error", "critical"])
    is_read = False
    extra_data = factory.LazyFunction(dict)
