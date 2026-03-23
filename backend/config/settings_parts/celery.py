"""Celery-related settings helpers."""

from __future__ import annotations

import os

from celery.schedules import crontab


def build_celery_settings(redis_url: str, redis_db: int) -> dict[str, object]:
    """Return Celery settings derived from the Redis configuration."""
    broker_url = redis_url.replace(f"/{redis_db}", "/2")
    return {
        "CELERY_BROKER_URL": broker_url,
        "CELERY_RESULT_BACKEND": broker_url,
        "CELERY_ACCEPT_CONTENT": ["json"],
        "CELERY_TASK_SERIALIZER": "json",
        "CELERY_RESULT_SERIALIZER": "json",
        "CELERY_TIMEZONE": "UTC",
        "CELERY_ENABLE_UTC": True,
        "CELERY_WORKER_LOG_FORMAT": (
            "[%(asctime)s: %(levelname)s/%(processName)s] [%(name)s] %(message)s"
        ),
        "CELERY_WORKER_TASK_LOG_FORMAT": (
            "[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s"
        ),
        "CELERY_TASK_DEFAULT_QUEUE": os.getenv("CELERY_TASK_DEFAULT_QUEUE", "default"),
        "CELERY_TASK_ROUTES": {
            # System queue: control-plane tasks (supervisors, recovery, health)
            "market.tasks.ensure_tick_pubsub_running": {"queue": "system"},
            "trading.tasks.recover_orphaned_tasks": {"queue": "system"},
            # Market queue: data ingestion and streaming
            "market.tasks.publish_oanda_ticks": {"queue": "market"},
            "market.tasks.subscribe_ticks_to_db": {"queue": "market"},
            "market.tasks.load_daily_tick_data": {"queue": "market"},
            # Backtest queue: historical data replay
            "market.tasks.publish_ticks_for_backtest": {"queue": "backtest"},
            "trading.tasks.run_backtest_task": {"queue": "backtest"},
            "trading.tasks.stop_backtest_task": {"queue": "backtest"},
            # Trading queue: live execution
            "trading.tasks.run_trading_task": {"queue": "trading"},
            "trading.tasks.stop_trading_task": {"queue": "trading"},
            # Default queue: infrastructure tasks
            "config.tasks.backup_database": {"queue": "default"},
        },
        "CELERY_BEAT_SCHEDULE": {
            "recover-orphaned-tasks": {
                "task": "trading.tasks.recover_orphaned_tasks",
                "schedule": 300,
                "options": {"queue": "system"},
            },
            "cleanup-expired-refresh-tokens": {
                "task": "accounts.tasks.cleanup_expired_refresh_tokens",
                "schedule": 3600,
                "options": {"queue": "default"},
            },
            "load-daily-tick-data": {
                "task": "market.tasks.load_daily_tick_data",
                "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
                "options": {"queue": "market"},
            },
            "backup-database": {
                "task": "config.tasks.backup_database",
                "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
                "options": {"queue": "default"},
            },
        },
    }
