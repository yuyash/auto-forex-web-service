from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="trade",
            name="layer_index",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="Layer index for Floor strategy-related trades",
                null=True,
            ),
        ),
    ]

