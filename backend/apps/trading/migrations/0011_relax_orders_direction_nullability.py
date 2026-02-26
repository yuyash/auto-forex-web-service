from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0010_rename_strategy_ev_task_ty_6200fd_idx_strategy_ev_task_ty_4e27cc_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="direction",
            field=models.CharField(
                blank=True,
                choices=[("long", "Long"), ("short", "Short")],
                help_text="Order direction (LONG/SHORT). Null for trade-close orders (e.g. take profit).",
                max_length=10,
                null=True,
            ),
        ),
    ]
