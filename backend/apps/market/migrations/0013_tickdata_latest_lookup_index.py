"""Add latest tick lookup index."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add composite index for latest tick lookups by instrument."""

    dependencies = [
        ("market", "0012_oandaretrymetric"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="tickdata",
            index=models.Index(
                fields=["instrument", "-timestamp"],
                name="tick_instr_ts_desc_idx",
            ),
        ),
    ]
