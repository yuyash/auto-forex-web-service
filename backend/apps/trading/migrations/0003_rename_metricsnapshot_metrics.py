"""Rename MetricSnapshot model to Metrics."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0002_add_metrics_json_to_metric_snapshot"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="MetricSnapshot",
            new_name="Metrics",
        ),
    ]
