"""Integration tests for trading models."""

import pytest
from django.utils import timezone

from apps.trading.enums import TaskStatus
from apps.trading.models import (
    BacktestTask,
    CeleryTaskStatus,
    StrategyConfiguration,
    TradingTask,
)
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestStrategyConfiguration:
    def test_create_for_user(self):
        user = UserFactory()
        config = StrategyConfiguration.objects.create_for_user(
            user, name="Test Config", strategy_type="floor", parameters={"instrument": "USD_JPY"}
        )
        assert config.user == user
        assert config.name == "Test Config"

    def test_for_user_queryset(self):
        user = UserFactory()
        StrategyConfigurationFactory(user=user)
        StrategyConfigurationFactory(user=user)
        other_user = UserFactory()
        StrategyConfigurationFactory(user=other_user)
        assert StrategyConfiguration.objects.for_user(user).count() == 2

    def test_is_in_use_false(self):
        config = StrategyConfigurationFactory()
        assert config.is_in_use() is False

    def test_is_in_use_with_backtest(self):
        config = StrategyConfigurationFactory()
        BacktestTaskFactory(user=config.user, config=config)
        assert config.is_in_use() is True

    def test_is_in_use_with_trading(self):
        config = StrategyConfigurationFactory()
        account = OandaAccountFactory(user=config.user)
        TradingTaskFactory(user=config.user, config=config, oanda_account=account)
        assert config.is_in_use() is True

    def test_validate_parameters_valid(self):
        config = StrategyConfigurationFactory()
        is_valid, error = config.validate_parameters()
        assert is_valid is True

    def test_validate_parameters_invalid_type(self):
        config = StrategyConfigurationFactory(strategy_type="nonexistent")
        is_valid, error = config.validate_parameters()
        assert is_valid is False

    def test_to_dict(self):
        config = StrategyConfigurationFactory()
        d = config.to_dict()
        assert "id" in d
        assert "name" in d
        assert "strategy_type" in d

    def test_config_dict_property(self):
        config = StrategyConfigurationFactory(parameters={"key": "value"})
        assert config.config_dict == {"key": "value"}

    def test_unique_name_per_user(self):
        user = UserFactory()
        StrategyConfigurationFactory(user=user, name="Unique Name")
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            StrategyConfigurationFactory(user=user, name="Unique Name")


@pytest.mark.django_db
class TestTradingTaskModel:
    def test_create_task(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        account = OandaAccountFactory(user=user)
        task = TradingTask.objects.create(
            user=user, config=config, oanda_account=account, name="Test Task"
        )
        assert task.status == TaskStatus.CREATED
        assert task.pk is not None

    def test_for_user(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        account = OandaAccountFactory(user=user)
        TradingTaskFactory(user=user, config=config, oanda_account=account)
        assert TradingTask.objects.for_user(user).count() == 1

    def test_duration_none_when_not_started(self):
        task = TradingTaskFactory()
        assert task.duration is None

    def test_duration_calculated(self):
        task = TradingTaskFactory()
        task.started_at = timezone.now()
        task.completed_at = task.started_at + timezone.timedelta(seconds=120)
        assert task.duration.total_seconds() == 120

    def test_copy(self):
        task = TradingTaskFactory()
        new_task = task.copy("New Name")
        assert new_task.name == "New Name"
        assert new_task.config == task.config
        assert new_task.status == TaskStatus.CREATED

    def test_copy_same_name_raises(self):
        task = TradingTaskFactory()
        with pytest.raises(ValueError, match="different"):
            task.copy(task.name)

    def test_delete_running_raises(self):
        task = TradingTaskFactory(status=TaskStatus.RUNNING)
        with pytest.raises(ValueError, match="Cannot delete"):
            task.delete()

    def test_delete_stopped_succeeds(self):
        task = TradingTaskFactory(status=TaskStatus.STOPPED)
        task.delete()
        assert not TradingTask.objects.filter(pk=task.pk).exists()

    def test_validate_configuration(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        account = OandaAccountFactory(user=user)
        task = TradingTaskFactory(user=user, config=config, oanda_account=account)
        is_valid, error = task.validate_configuration()
        assert is_valid is True

    def test_has_strategy_state_false(self):
        task = TradingTaskFactory()
        assert task.has_strategy_state() is False

    def test_has_strategy_state_true(self):
        task = TradingTaskFactory(strategy_state={"key": "value"})
        assert task.has_strategy_state() is True

    def test_can_resume_false_when_running(self):
        task = TradingTaskFactory(status=TaskStatus.RUNNING)
        assert task.can_resume() is False

    def test_can_resume_true_when_stopped_with_state(self):
        task = TradingTaskFactory(status=TaskStatus.STOPPED, strategy_state={"key": "value"})
        assert task.can_resume() is True

    def test_unique_name_per_user(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        account = OandaAccountFactory(user=user)
        TradingTaskFactory(user=user, config=config, oanda_account=account, name="Same Name")
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            TradingTaskFactory(user=user, config=config, oanda_account=account, name="Same Name")


@pytest.mark.django_db
class TestBacktestTaskModel:
    def test_create_task(self):
        task = BacktestTaskFactory()
        assert task.pk is not None

    def test_for_user(self):
        user = UserFactory()
        config = StrategyConfigurationFactory(user=user)
        BacktestTaskFactory(user=user, config=config)
        assert BacktestTask.objects.for_user(user).count() == 1

    def test_duration_none(self):
        task = BacktestTaskFactory()
        assert task.duration is None

    def test_copy(self):
        task = BacktestTaskFactory()
        new_task = task.copy("New Backtest")
        assert new_task.name == "New Backtest"
        assert new_task.status == TaskStatus.CREATED

    def test_delete_running_raises(self):
        task = BacktestTaskFactory(status=TaskStatus.RUNNING)
        with pytest.raises(ValueError, match="Cannot delete"):
            task.delete()

    def test_validate_configuration(self):
        task = BacktestTaskFactory()
        is_valid, error = task.validate_configuration()
        assert is_valid is True


@pytest.mark.django_db
class TestCeleryTaskStatus:
    def test_start_task(self):
        status = CeleryTaskStatus.objects.start_task(
            task_name="test.task", instance_key="123", celery_task_id="c-1", worker="w1"
        )
        assert status.status == CeleryTaskStatus.Status.RUNNING
        assert status.celery_task_id == "c-1"

    def test_start_task_updates_existing(self):
        CeleryTaskStatus.objects.start_task(task_name="test.task", instance_key="123")
        status = CeleryTaskStatus.objects.start_task(
            task_name="test.task", instance_key="123", celery_task_id="c-2"
        )
        assert status.celery_task_id == "c-2"
        assert (
            CeleryTaskStatus.objects.filter(task_name="test.task", instance_key="123").count() == 1
        )

    def test_heartbeat(self):
        status = CeleryTaskStatus.objects.start_task(task_name="test.task", instance_key="hb")
        status.heartbeat(status_message="alive")
        status.refresh_from_db()
        assert status.status_message == "alive"

    def test_heartbeat_with_meta(self):
        status = CeleryTaskStatus.objects.start_task(task_name="test.task", instance_key="meta")
        status.heartbeat(meta_update={"ticks": 100})
        status.refresh_from_db()
        assert status.meta["ticks"] == 100

    def test_mark_stopped(self):
        status = CeleryTaskStatus.objects.start_task(task_name="test.task", instance_key="stop")
        status.mark_stopped()
        status.refresh_from_db()
        assert status.status == CeleryTaskStatus.Status.STOPPED
        assert status.stopped_at is not None

    def test_mark_completed(self):
        status = CeleryTaskStatus.objects.start_task(task_name="test.task", instance_key="comp")
        status.mark_stopped(status=CeleryTaskStatus.Status.COMPLETED)
        status.refresh_from_db()
        assert status.status == CeleryTaskStatus.Status.COMPLETED

    def test_mark_failed(self):
        status = CeleryTaskStatus.objects.start_task(task_name="test.task", instance_key="fail")
        status.mark_stopped(status=CeleryTaskStatus.Status.FAILED, status_message="error occurred")
        status.refresh_from_db()
        assert status.status == CeleryTaskStatus.Status.FAILED
        assert status.status_message == "error occurred"

    def test_normalize_instance_key(self):
        assert CeleryTaskStatus.objects.normalize_instance_key(None) == "default"
        assert CeleryTaskStatus.objects.normalize_instance_key("abc") == "abc"
