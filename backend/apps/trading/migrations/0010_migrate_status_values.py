"""
Generated migration for status value mapping.

This migration updates existing status values to use the new enum-based system.
"""

# pylint: disable=unused-argument,invalid-name

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def migrate_backtest_status(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """
    Migrate existing Backtest status values to new enum values.

    Old values -> New values:
    - pending -> created
    - running -> running (no change)
    - completed -> completed (no change)
    - failed -> failed (no change)
    - cancelled -> stopped
    - terminated -> failed
    """
    Backtest = apps.get_model("trading", "Backtest")

    # Map old status values to new enum values
    status_mapping = {
        "pending": "created",
        "cancelled": "stopped",
        "terminated": "failed",
    }

    for old_status, new_status in status_mapping.items():
        Backtest.objects.filter(status=old_status).update(status=new_status)


def migrate_strategy_status(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """
    Migrate existing Strategy is_active values to status field.

    is_active=True -> status=running
    is_active=False -> status=stopped
    """
    Strategy = apps.get_model("trading", "Strategy")

    # Update strategies based on is_active field
    Strategy.objects.filter(is_active=True).update(status="running")
    Strategy.objects.filter(is_active=False).update(status="stopped")


def migrate_comparison_status(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """
    Migrate existing StrategyComparison status values to new enum values.

    Old values -> New values:
    - pending -> created
    - running -> running (no change)
    - completed -> completed (no change)
    - failed -> failed (no change)
    """
    StrategyComparison = apps.get_model("trading", "StrategyComparison")

    # Map old status values to new enum values
    StrategyComparison.objects.filter(status="pending").update(status="created")


def reverse_backtest_status(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Reverse migration for Backtest status."""
    Backtest = apps.get_model("trading", "Backtest")

    # Reverse mapping
    Backtest.objects.filter(status="created").update(status="pending")
    Backtest.objects.filter(status="stopped").update(status="cancelled")


def reverse_strategy_status(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Reverse migration for Strategy status."""
    # No reverse needed as is_active field is maintained


def reverse_comparison_status(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Reverse migration for StrategyComparison status."""
    StrategyComparison = apps.get_model("trading", "StrategyComparison")

    # Reverse mapping
    StrategyComparison.objects.filter(status="created").update(status="pending")


class Migration(migrations.Migration):
    """Migration to update status values to use enum-based system."""

    dependencies = [
        ("trading", "0009_add_enum_fields"),
    ]

    operations = [
        migrations.RunPython(
            migrate_backtest_status,
            reverse_backtest_status,
        ),
        migrations.RunPython(
            migrate_strategy_status,
            reverse_strategy_status,
        ),
        migrations.RunPython(
            migrate_comparison_status,
            reverse_comparison_status,
        ),
    ]
