from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0028_trading_celery_task_status"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="celerytaskstatus",
            table="trading_celery_tasks",
        ),
    ]
