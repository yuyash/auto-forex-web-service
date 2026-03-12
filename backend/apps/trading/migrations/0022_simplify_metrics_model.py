"""Remove legacy per-field metric columns; keep only JSON metrics field.

Also truncates the metrics table since existing tick-level data is no
longer compatible with the new minute-level aggregation scheme.
"""

from django.db import migrations, models


def _truncate_metrics(apps, schema_editor):
    """Delete all existing metrics data (tick-level, incompatible)."""
    schema_editor.execute("DELETE FROM metrics")


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0021_alter_order_broker_order_id_to_textfield"),
    ]

    operations = [
        # Wipe existing tick-level data
        migrations.RunPython(_truncate_metrics, migrations.RunPython.noop),
        # Drop legacy columns
        migrations.RemoveField(model_name="metrics", name="margin_ratio"),
        migrations.RemoveField(model_name="metrics", name="current_atr"),
        migrations.RemoveField(model_name="metrics", name="baseline_atr"),
        migrations.RemoveField(model_name="metrics", name="volatility_threshold"),
    ]
