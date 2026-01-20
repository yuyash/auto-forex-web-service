"""
Management command to manually trigger execution monitoring.

This command can be used to check for stuck executions and sync
Celery task status without waiting for the periodic tasks.
"""

from django.core.management.base import BaseCommand

from apps.trading.tasks.monitoring import monitor_stuck_executions, sync_celery_task_status


class Command(BaseCommand):
    """Monitor and clean up stuck executions."""

    help = "Monitor for stuck executions and sync Celery task status"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--sync-only",
            action="store_true",
            help="Only sync Celery task status, skip stuck execution monitoring",
        )
        parser.add_argument(
            "--monitor-only",
            action="store_true",
            help="Only monitor stuck executions, skip Celery task sync",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        sync_only = options.get("sync_only", False)
        monitor_only = options.get("monitor_only", False)

        if not sync_only:
            self.stdout.write(self.style.WARNING("Monitoring stuck executions..."))
            results = monitor_stuck_executions()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Found and cleaned up {results['stuck_count']} stuck executions"
                )
            )
            if results["cleaned_up"]:
                for item in results["cleaned_up"]:
                    self.stdout.write(
                        f"  - Execution {item['execution_id']} "
                        f"({item['task_type']} task {item['task_id']})"
                    )
            if results["errors"]:
                self.stdout.write(self.style.ERROR(f"Errors: {len(results['errors'])}"))
                for error in results["errors"]:
                    self.stdout.write(f"  - {error}")

        if not monitor_only:
            self.stdout.write(self.style.WARNING("\nSyncing Celery task status..."))
            results = sync_celery_task_status()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Active Celery tasks: {results['active_celery_tasks']}, "
                    f"Orphaned executions: {results['orphaned_count']}"
                )
            )
            if results["synced"]:
                for item in results["synced"]:
                    self.stdout.write(
                        f"  - Execution {item['execution_id']} "
                        f"({item['task_type']} task {item['task_id']})"
                    )
            if results["errors"]:
                self.stdout.write(self.style.ERROR(f"Errors: {len(results['errors'])}"))
                for error in results["errors"]:
                    self.stdout.write(f"  - {error}")

        self.stdout.write(self.style.SUCCESS("\n✓ Monitoring complete"))
