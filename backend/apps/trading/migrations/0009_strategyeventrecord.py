from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "accounts",
            "0002_rename_account_sec_categor_582846_idx_account_sec_categor_ebfc3a_idx_and_more",
        ),
        ("market", "0002_alter_celerytaskstatus_status"),
        ("trading", "0008_tradingevent_is_processed_tradingevent_processed_at_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="StrategyEventRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(db_index=True, max_length=64)),
                ("severity", models.CharField(db_index=True, default="info", max_length=16)),
                ("description", models.TextField()),
                ("instrument", models.CharField(blank=True, db_index=True, max_length=32, null=True)),
                ("task_type", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("task_id", models.UUIDField(blank=True, db_index=True, null=True)),
                (
                    "execution_run_id",
                    models.PositiveIntegerField(
                        db_index=True,
                        default=0,
                        help_text="Execution run identifier for run-scoped event queries",
                    ),
                ),
                (
                    "celery_task_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Celery task ID for tracking specific execution",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="strategy_events",
                        to="market.oandaaccounts",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="strategy_events",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Strategy Event",
                "verbose_name_plural": "Strategy Events",
                "db_table": "strategy_events",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="strategyeventrecord",
            index=models.Index(fields=["task_type", "task_id", "-created_at"], name="strategy_ev_task_ty_6200fd_idx"),
        ),
        migrations.AddIndex(
            model_name="strategyeventrecord",
            index=models.Index(
                fields=["task_type", "task_id", "execution_run_id", "-created_at"],
                name="strategy_ev_task_ty_2b7ae0_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="strategyeventrecord",
            index=models.Index(fields=["event_type", "-created_at"], name="strategy_ev_event_t_80f0f9_idx"),
        ),
    ]
