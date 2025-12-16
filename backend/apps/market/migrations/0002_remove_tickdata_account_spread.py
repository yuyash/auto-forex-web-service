from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="tickdata",
            name="tick_data_account_0fb6f6_idx",
        ),
        migrations.RemoveField(
            model_name="tickdata",
            name="spread",
        ),
        migrations.RemoveField(
            model_name="tickdata",
            name="account",
        ),
    ]
