from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("trading", "0011_relax_orders_direction_nullability"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE trades ALTER COLUMN direction DROP NOT NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
