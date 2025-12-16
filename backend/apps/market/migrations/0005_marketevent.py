from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market", "0004_remove_oandaaccount_status_position_diff_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("event_type", models.CharField(db_index=True, max_length=64)),
                ("category", models.CharField(db_index=True, default="market", max_length=32)),
                ("severity", models.CharField(db_index=True, default="info", max_length=16)),
                ("description", models.TextField()),
                (
                    "instrument",
                    models.CharField(blank=True, db_index=True, max_length=32, null=True),
                ),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="market_events",
                        to="market.oandaaccount",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="market_events",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "db_table": "market_events",
                "verbose_name": "Market Event",
                "verbose_name_plural": "Market Events",
                "ordering": ["-created_at"],
            },
        ),
    ]
