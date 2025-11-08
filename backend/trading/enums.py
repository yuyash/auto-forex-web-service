"""
Enums for trading models.

This module contains enum definitions for:
- DataSource: Data source options for backtesting
- TaskStatus: Task lifecycle states
- TaskType: Types of tasks (backtest or trading)

Requirements: 1.2, 2.1, 3.1, 4.1
"""

# pylint: disable=too-many-ancestors

from django.db import models


class DataSource(models.TextChoices):
    """
    Data source options for backtesting.

    Requirements: 1.2, 2.1
    """

    POSTGRESQL = "postgresql", "PostgreSQL"
    ATHENA = "athena", "AWS Athena"


class TaskStatus(models.TextChoices):
    """
    Task lifecycle states.

    Requirements: 2.1, 3.1, 4.1
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

    Requirements: 4.1
    """

    BACKTEST = "backtest", "Backtest"
    TRADING = "trading", "Trading"
