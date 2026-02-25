"""Rename metric_snapshots table to metrics and update constraint/index names."""

from django.db import migrations, models


def _rename_metric_constraint_forward(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        'ALTER TABLE metrics RENAME CONSTRAINT "unique_metric_snapshot_timestamp" TO "unique_metric_timestamp"'
    )


def _rename_metric_constraint_backward(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        'ALTER TABLE metrics RENAME CONSTRAINT "unique_metric_timestamp" TO "unique_metric_snapshot_timestamp"'
    )


def _rename_metric_indexes_forward(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        'ALTER INDEX "metric_snap_task_ty_3909a0_idx" RENAME TO "metrics_task_ty_62aaf4_idx"'
    )
    schema_editor.execute(
        'ALTER INDEX "metric_snap_task_ty_cc1ce9_idx" RENAME TO "metrics_task_ty_309c89_idx"'
    )


def _rename_metric_indexes_backward(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        'ALTER INDEX "metrics_task_ty_62aaf4_idx" RENAME TO "metric_snap_task_ty_3909a0_idx"'
    )
    schema_editor.execute(
        'ALTER INDEX "metrics_task_ty_309c89_idx" RENAME TO "metric_snap_task_ty_cc1ce9_idx"'
    )


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0003_rename_metricsnapshot_metrics"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="metrics",
            table="metrics",
        ),
        # Rename constraint: Django state tracks the old name from the
        # MetricSnapshot era.  SeparateDatabaseAndState ensures both the
        # real DB constraint AND Django's internal state are updated.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    _rename_metric_constraint_forward,
                    _rename_metric_constraint_backward,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="metrics",
                    name="unique_metric_snapshot_timestamp",
                ),
                migrations.AddConstraint(
                    model_name="metrics",
                    constraint=models.UniqueConstraint(
                        fields=["task_type", "task_id", "celery_task_id", "timestamp"],
                        name="unique_metric_timestamp",
                    ),
                ),
            ],
        ),
        # Rename indexes: the auto-generated index names changed because
        # the db_table changed from metric_snapshots to metrics.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    _rename_metric_indexes_forward,
                    _rename_metric_indexes_backward,
                ),
            ],
            state_operations=[
                migrations.RenameIndex(
                    model_name="metrics",
                    new_name="metrics_task_ty_62aaf4_idx",
                    old_name="metric_snap_task_ty_3909a0_idx",
                ),
                migrations.RenameIndex(
                    model_name="metrics",
                    new_name="metrics_task_ty_309c89_idx",
                    old_name="metric_snap_task_ty_cc1ce9_idx",
                ),
            ],
        ),
    ]
