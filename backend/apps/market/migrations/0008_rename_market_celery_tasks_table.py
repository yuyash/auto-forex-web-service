from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0007_rename_managedcelerytask_to_celerytaskstatus"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="celerytaskstatus",
            table="market_celery_tasks",
        ),
    ]
