# Generated migration to remove realized_pnl from Position model.
#
# PnL is now computed on-the-fly from (exit_price - entry_price) * units,
# adjusted for direction.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0017_remove_position_unrealized_pnl"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="position",
            name="realized_pnl",
        ),
    ]
