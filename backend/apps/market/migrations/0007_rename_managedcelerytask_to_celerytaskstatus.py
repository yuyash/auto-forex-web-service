from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0006_managedcelerytask"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ManagedCeleryTask",
            new_name="CeleryTaskStatus",
        ),
        migrations.AlterModelOptions(
            name="celerytaskstatus",
            options={
                "db_table": "market_managed_celery_tasks",
                "verbose_name": "Celery Task Status",
                "verbose_name_plural": "Celery Task Statuses",
            },
        ),
    ]
