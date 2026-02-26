from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0010_rename_strategy_ev_task_ty_6200fd_idx_strategy_ev_task_ty_4e27cc_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE orders ALTER COLUMN direction DROP NOT NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
