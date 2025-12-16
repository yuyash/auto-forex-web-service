from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0005_marketevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManagedCeleryTask",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("task_name", models.CharField(db_index=True, max_length=200)),
                (
                    "instance_key",
                    models.CharField(blank=True, db_index=True, default="default", max_length=200),
                ),
                (
                    "celery_task_id",
                    models.CharField(blank=True, db_index=True, max_length=200, null=True),
                ),
                ("worker", models.CharField(blank=True, max_length=200, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("stop_requested", "Stop Requested"),
                            ("stopped", "Stopped"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="running",
                        max_length=32,
                    ),
                ),
                ("status_message", models.TextField(blank=True, null=True)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("last_heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("stopped_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "market_managed_celery_tasks",
                "verbose_name": "Managed Celery Task",
                "verbose_name_plural": "Managed Celery Tasks",
            },
        ),
        migrations.AddConstraint(
            model_name="managedcelerytask",
            constraint=models.UniqueConstraint(
                fields=("task_name", "instance_key"),
                name="uniq_market_task_name_instance_key",
            ),
        ),
        migrations.AddIndex(
            model_name="managedcelerytask",
            index=models.Index(
                fields=["task_name", "status"], name="market_mana_task_na_57e1fc_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="managedcelerytask",
            index=models.Index(fields=["celery_task_id"], name="market_mana_celery__e5025a_idx"),
        ),
        migrations.AddIndex(
            model_name="managedcelerytask",
            index=models.Index(fields=["last_heartbeat_at"], name="market_mana_last_he_d7d6f2_idx"),
        ),
    ]
