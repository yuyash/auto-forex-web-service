from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0002_remove_tickdata_account_spread"),
    ]

    operations = [
        migrations.AddField(
            model_name="oandaaccounts",
            name="is_used",
            field=models.BooleanField(
                default=False,
                help_text="Whether this account is currently used by any running process",
            ),
        ),
    ]
