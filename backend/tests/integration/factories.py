"""
Test data factories for integration tests.

This module provides Factory Boy factories for creating realistic test data
for integration tests. Factories use Faker to generate random but realistic
data values.
"""

import factory
from datetime import UTC
from django.utils import timezone
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


def _aware_datetime_between(start_date, end_date):
    dt = fake.date_time_between(start_date=start_date, end_date=end_date, tzinfo=UTC)
    return timezone.make_aware(dt, UTC) if timezone.is_naive(dt) else dt


class UserFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = User
        skip_postgeneration_save = True

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
        skip_postgeneration_save = True

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
    def set_encrypted_token(obj, create, extracted, **kwargs):
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
    timestamp = factory.LazyFunction(lambda: _aware_datetime_between("-30d", "now"))
    bid = factory.Faker(
        "pydecimal", left_digits=1, right_digits=5, positive=True, min_value=1.0, max_value=2.0
    )
    ask = factory.LazyAttribute(
        lambda obj: (
            obj.bid
            + fake.pydecimal(
                left_digits=0, right_digits=5, positive=True, min_value=0.00001, max_value=0.0001
            )
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
    start_time = factory.LazyFunction(lambda: _aware_datetime_between("-60d", "-1d"))
    end_time = factory.LazyAttribute(lambda obj: _aware_datetime_between(obj.start_time, "+30d"))
    initial_balance = factory.Faker(
        "pydecimal", left_digits=6, right_digits=2, positive=True, min_value=10000, max_value=100000
    )
    status = "created"
    data_source = "postgresql"
    celery_task_id = factory.Faker("uuid4")


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
    celery_task_id = factory.Faker("uuid4")


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
