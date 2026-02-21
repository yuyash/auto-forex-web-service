"""Remove open_price and open_timestamp fields from Trade model.

The price field already captures the execution price at the time of each
trade event, making open_price and open_timestamp redundant.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0013_remove_trade_close_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="trade",
            name="open_price",
        ),
        migrations.RemoveField(
            model_name="trade",
            name="open_timestamp",
        ),
    ]
