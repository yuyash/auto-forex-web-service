"""Celery-related settings helpers."""

from __future__ import annotations

import os


def build_celery_settings(redis_url: str, redis_db: int) -> dict[str, object]:
    """Return Celery settings derived from the Redis configuration."""
    broker_url = redis_url.replace(f"/{redis_db}", "/2")
    default_concurrency = int(os.getenv("CELERY_DEFAULT_WORKER_CONCURRENCY", "2"))
    control_concurrency = int(os.getenv("CELERY_CONTROL_WORKER_CONCURRENCY", "2"))
    market_concurrency = int(os.getenv("CELERY_MARKET_WORKER_CONCURRENCY", "3"))
    backtest_concurrency = int(os.getenv("CELERY_BACKTEST_WORKER_CONCURRENCY", "4"))
    backtest_publisher_concurrency = int(os.getenv("CELERY_BACKTEST_PUBLISHER_CONCURRENCY", "4"))
    trading_concurrency = int(os.getenv("CELERY_TRADING_WORKER_CONCURRENCY", "2"))
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
        "CELERY_WORKER_PREFETCH_MULTIPLIER": int(
            os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")
        ),
        "CELERY_DEFAULT_WORKER_CONCURRENCY": default_concurrency,
        "CELERY_CONTROL_WORKER_CONCURRENCY": control_concurrency,
        "CELERY_MARKET_WORKER_CONCURRENCY": market_concurrency,
        "CELERY_BACKTEST_WORKER_CONCURRENCY": backtest_concurrency,
        "CELERY_BACKTEST_PUBLISHER_CONCURRENCY": backtest_publisher_concurrency,
        "CELERY_TRADING_WORKER_CONCURRENCY": trading_concurrency,
        "CELERY_TASK_ROUTES": {
            # System queue: control-plane tasks (supervisors, recovery, health)
            "market.tasks.ensure_tick_pubsub_running": {"queue": "system"},
            "trading.tasks.recover_orphaned_tasks": {"queue": "system"},
            "trading.tasks.stop_backtest_task": {"queue": "system"},
            "trading.tasks.stop_trading_task": {"queue": "system"},
            # Market queue: data ingestion and streaming
            "market.tasks.publish_oanda_ticks": {"queue": "market"},
            "market.tasks.subscribe_ticks_to_db": {"queue": "market"},
            # Backtest queue: execution and historical data replay
            "market.tasks.publish_ticks_for_backtest": {"queue": "backtest_publisher"},
            "trading.tasks.run_backtest_task": {"queue": "backtest"},
            # Trading queue: live execution
            "trading.tasks.run_trading_task": {"queue": "trading"},
        },
        "CELERY_BEAT_SCHEDULE": {
            "ensure-tick-pubsub-running": {
                "task": "market.tasks.ensure_tick_pubsub_running",
                "schedule": 30,
                "options": {"queue": "system"},
            },
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
        },
    }
