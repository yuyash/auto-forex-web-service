# Generated migration to fix task_id field type mismatch

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0007_layer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tradingevent',
            name='task_id',
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
