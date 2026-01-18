from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0009_oanda_api_health_status"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="oandaaccounts",
            unique_together={("user", "account_id", "api_type")},
        ),
    ]
