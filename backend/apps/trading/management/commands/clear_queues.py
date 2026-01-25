"""Management command to clear Celery queues."""

import redis
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Clear Celery task queues."""

    help = "Clear Celery task queues"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--queue",
            type=str,
            help="Specific queue to clear (default: all)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleared without actually clearing",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        queue_name = options.get("queue")
        dry_run = options.get("dry_run", False)

        # Connect to Redis
        r = redis.from_url(settings.CELERY_BROKER_URL)

        # Define queues to check
        queues = [queue_name] if queue_name else ["celery", "trading", "market", "default"]

        self.stdout.write(self.style.SUCCESS("\n=== Celery Queue Status ==="))

        total_cleared = 0
        for queue in queues:
            length = r.llen(queue)
            if length > 0:
                self.stdout.write(f"\n{queue}: {length} tasks")
                if not dry_run:
                    cleared = r.delete(queue)
                    self.stdout.write(self.style.WARNING(f"  ✓ Cleared {length} tasks"))
                    total_cleared += length
                else:
                    self.stdout.write(self.style.WARNING(f"  Would clear {length} tasks"))
            else:
                self.stdout.write(f"{queue}: empty")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\n🔍 Dry run: Would clear {total_cleared} tasks total")
            )
        elif total_cleared > 0:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Cleared {total_cleared} tasks total"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ All queues are empty"))
