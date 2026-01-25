"""
Management command to manually trigger task status reconciliation.

This command can be used to reconcile task statuses with Celery
without waiting for the periodic task.
"""

from django.core.management.base import BaseCommand

from apps.trading.tasks.monitoring import reconcile_task_statuses


class Command(BaseCommand):
    """Reconcile task statuses with Celery."""

    help = "Reconcile task statuses with Celery task states"

    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write(self.style.WARNING("Reconciling task statuses..."))
        results = reconcile_task_statuses()

        self.stdout.write(self.style.SUCCESS(f"✓ Reconciled {results['reconciled_count']} tasks"))

        if results["reconciled_tasks"]:
            for item in results["reconciled_tasks"]:
                self.stdout.write(
                    f"  - {item['task_type'].title()} Task {item['task_id']} "
                    f"({item['task_name']}): {item['old_status']} -> {item['new_status']}"
                )

        if results["errors"]:
            self.stdout.write(self.style.ERROR(f"Errors: {len(results['errors'])}"))
            for error in results["errors"]:
                self.stdout.write(f"  - {error}")

        self.stdout.write(self.style.SUCCESS("\n✓ Reconciliation complete"))
