"""Remove legacy Position/Order/Trade models.

User-requested cleanup: the trading app no longer maintains these legacy tables.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0030_remove_strategy_models"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Order",
        ),
        migrations.DeleteModel(
            name="Position",
        ),
        migrations.DeleteModel(
            name="Trade",
        ),
    ]
