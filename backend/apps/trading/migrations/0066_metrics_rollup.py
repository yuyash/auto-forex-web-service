import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0065_snowball_rebuild_entry_mode_cleanup"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetricsRollup",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("task_type", models.CharField(max_length=32)),
                ("task_id", models.UUIDField()),
                (
                    "execution_id",
                    models.UUIDField(
                        blank=True,
                        help_text="Execution run UUID (shared with Celery task_id)",
                        null=True,
                    ),
                ),
                (
                    "granularity",
                    models.CharField(
                        help_text="Bucket granularity token such as M5, M15, H1, H4, or D.",
                        max_length=8,
                    ),
                ),
                ("bucket", models.DateTimeField(help_text="Start timestamp of the rollup bucket")),
                (
                    "source_timestamp",
                    models.DateTimeField(
                        help_text="Timestamp of the source metrics row represented by this bucket"
                    ),
                ),
                (
                    "metrics",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Latest strategy metrics snapshot for this bucket",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "metrics_rollups",
                "ordering": ["bucket"],
            },
        ),
        migrations.AddIndex(
            model_name="metricsrollup",
            index=models.Index(
                fields=["task_type", "task_id", "execution_id", "granularity", "bucket"],
                name="metrics_roll_scope_bucket_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="metricsrollup",
            constraint=models.UniqueConstraint(
                fields=["task_type", "task_id", "execution_id", "granularity", "bucket"],
                name="uniq_metrics_rollup_bucket",
                nulls_distinct=False,
            ),
        ),
    ]
