"""Remove pnl field from Trade model.

PnL is tracked on the positions table via realized_pnl.
Trades are purely append-only event records.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0014_remove_trade_open_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="trade",
            name="pnl",
        ),
    ]
