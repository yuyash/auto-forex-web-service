"""Populate pip_size for existing tasks that have NULL values."""

from decimal import Decimal

from django.db import migrations

# JPY-quoted pairs use 0.01; all others use 0.0001
_JPY_QUOTES = {"JPY", "HUF"}


def _pip_size(instrument: str) -> Decimal:
    quote = instrument.split("_")[-1].upper() if "_" in instrument else ""
    return Decimal("0.01") if quote in _JPY_QUOTES else Decimal("0.0001")


def populate_pip_size(apps, schema_editor):
    TradingTask = apps.get_model("trading", "TradingTask")
    BacktestTask = apps.get_model("trading", "BacktestTask")

    for Model in (TradingTask, BacktestTask):
        for task in Model.objects.filter(pip_size__isnull=True):
            task.pip_size = _pip_size(task.instrument)
            task.save(update_fields=["pip_size"])


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0008_add_retracement_count_to_trade"),
    ]

    operations = [
        migrations.RunPython(populate_pip_size, migrations.RunPython.noop),
    ]
