"""Unit tests for trading tasks state manager."""

import json
from unittest.mock import patch

import fakeredis

from apps.trading.tasks.state import StateManager


class TestStateManager:
    def _make_manager(self, **kwargs):
        with patch("apps.trading.tasks.state.redis.Redis.from_url") as mock_redis:
            fake = fakeredis.FakeRedis(decode_responses=True)
            mock_redis.return_value = fake
            mgr = StateManager(
                task_name="test.task",
                instance_key="123",
                task_id=1,
                redis_url="redis://localhost:6379/0",
                **kwargs,
            )
            mgr.redis = fake
            return mgr

    def test_start_sets_running(self):
        mgr = self._make_manager()
        mgr.start(celery_task_id="celery-1", worker="w1")
        status = mgr.redis.hget(mgr.redis_key, "status")
        assert status == "running"

    def test_heartbeat_updates_timestamp(self):
        mgr = self._make_manager(heartbeat_interval_seconds=0)
        mgr.start()
        mgr.heartbeat(force=True, status_message="alive")
        msg = mgr.redis.hget(mgr.redis_key, "status_message")
        assert msg == "alive"

    def test_heartbeat_throttled(self):
        mgr = self._make_manager(heartbeat_interval_seconds=9999)
        mgr.start()
        mgr._last_heartbeat = 999999999
        mgr.heartbeat(status_message="should be throttled")
        msg = mgr.redis.hget(mgr.redis_key, "status_message")
        assert msg != "should be throttled"

    def test_check_control_no_stop(self):
        mgr = self._make_manager(stop_check_interval_seconds=0)
        mgr.start()
        with patch("apps.trading.models.BacktestTask") as mock_bt:
            mock_bt.objects.filter.return_value.values_list.return_value.first.return_value = (
                "running"
            )
            ctrl = mgr.check_control(force=True)
        assert ctrl.should_stop is False

    def test_check_control_stop_signal(self):
        mgr = self._make_manager(stop_check_interval_seconds=0)
        mgr.start()
        mgr.redis.hset(mgr.redis_key, "status", "stopping")
        with patch("apps.trading.models.BacktestTask") as mock_bt:
            mock_bt.objects.filter.return_value.values_list.return_value.first.return_value = None
            with patch("apps.trading.models.TradingTask") as mock_tt:
                mock_tt.objects.filter.return_value.values_list.return_value.first.return_value = (
                    None
                )
                ctrl = mgr.check_control(force=True)
        assert ctrl.should_stop is True

    def test_stop_marks_stopped(self):
        mgr = self._make_manager()
        mgr.start()
        mgr.stop()
        status = mgr.redis.hget(mgr.redis_key, "status")
        assert status == "stopped"

    def test_stop_marks_completed(self):
        mgr = self._make_manager()
        mgr.start()
        mgr.stop(completed=True)
        status = mgr.redis.hget(mgr.redis_key, "status")
        assert status == "completed"

    def test_stop_marks_failed(self):
        mgr = self._make_manager()
        mgr.start()
        mgr.stop(failed=True)
        status = mgr.redis.hget(mgr.redis_key, "status")
        assert status == "failed"

    def test_cleanup(self):
        mgr = self._make_manager()
        mgr.start()
        mgr.cleanup()
        assert mgr.redis.exists(mgr.redis_key) == 1

    def test_cleanup_with_delete_key(self):
        mgr = self._make_manager()
        mgr.start()
        mgr.cleanup(delete_key=True)
        assert mgr.redis.exists(mgr.redis_key) == 0

    def test_heartbeat_with_meta_update(self):
        mgr = self._make_manager(heartbeat_interval_seconds=0)
        mgr.start()
        mgr.heartbeat(force=True, meta_update={"ticks": 100})
        meta_str = mgr.redis.hget(mgr.redis_key, "meta")
        meta = json.loads(meta_str)
        assert meta["ticks"] == 100
