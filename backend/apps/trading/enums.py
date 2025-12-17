"""
Enums for trading models.

This module contains enum definitions for:
- DataSource: Data source options for backtesting
- TaskStatus: Task lifecycle states
- TaskType: Types of tasks (backtest or trading)
"""

from django.db import models


class DataSource(models.TextChoices):
    """
    Data source options for backtesting.
    """

    POSTGRESQL = "postgresql", "PostgreSQL"
    ATHENA = "athena", "AWS Athena"
    S3 = "s3", "AWS S3"


class TaskStatus(models.TextChoices):
    """
    Task lifecycle states.
    """

    CREATED = "created", "Created"
    RUNNING = "running", "Running"
    STOPPED = "stopped", "Stopped"
    PAUSED = "paused", "Paused"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class TaskType(models.TextChoices):
    """
    Types of tasks.
    """

    BACKTEST = "backtest", "Backtest"
    TRADING = "trading", "Trading"


class StopMode(models.TextChoices):
    """
    Stop modes for trading tasks.

    - IMMEDIATE: Stop immediately without closing positions (fastest)
    - GRACEFUL: Stop gracefully, wait for pending operations to complete
    - GRACEFUL_CLOSE: Stop gracefully and close all open positions
    """

    IMMEDIATE = "immediate", "Immediate Stop"
    GRACEFUL = "graceful", "Graceful Stop (Keep Positions)"
    GRACEFUL_CLOSE = "graceful_close", "Graceful Stop (Close Positions)"
