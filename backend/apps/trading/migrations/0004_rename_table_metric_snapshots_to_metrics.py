"""Rename metric_snapshots table to metrics and update constraint name."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0003_rename_metricsnapshot_metrics"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="metrics",
            table="metrics",
        ),
        migrations.RunSQL(
            sql='ALTER TABLE metrics RENAME CONSTRAINT "unique_metric_snapshot_timestamp" TO "unique_metric_timestamp"',
            reverse_sql='ALTER TABLE metrics RENAME CONSTRAINT "unique_metric_timestamp" TO "unique_metric_snapshot_timestamp"',
        ),
    ]
