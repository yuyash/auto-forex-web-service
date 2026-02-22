"""Task management signal handlers."""

from __future__ import annotations

from logging import Logger, getLogger

from django.utils.timezone import now as django_now

from apps.market.models import CeleryTaskStatus
from apps.market.signals.base import SignalHandler, market_task_cancel_requested

logger: Logger = getLogger(name=__name__)


class TaskManagementSignalHandler(SignalHandler):
    """Handler for task management signals."""

    def connect(self) -> None:
        """Connect task management signal handlers."""
        market_task_cancel_requested.connect(
            self.handle_market_task_cancel_requested,
            dispatch_uid="market.signals.handle_market_task_cancel_requested",
        )

    def request_market_task_cancel(
        self,
        *,
        task_name: str,
        instance_key: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Request cancellation of a market task.

        Args:
            task_name: Name of the task to cancel
            instance_key: Instance key (defaults to "default")
            reason: Optional reason for cancellation
        """
        key = instance_key or "default"
        market_task_cancel_requested.send(
            sender=self.__class__,
            task_name=task_name,
            instance_key=key,
            reason=reason,
        )

    def handle_market_task_cancel_requested(
        self,
        sender: object,
        signal: object,
        *,
        task_name: str,
        instance_key: str | None = None,
        reason: str | None = None,
        **_kwargs: object,
    ) -> None:
        """Handle market task cancellation request.

        Sets task status to STOP_REQUESTED. Tasks are responsible for
        honoring this flag and stopping gracefully.
        """
        key = instance_key or "default"
        now = django_now()
        qs = CeleryTaskStatus.objects.filter(task_name=str(task_name), instance_key=key)

        updated = qs.exclude(status=CeleryTaskStatus.Status.STOPPED).update(
            status=CeleryTaskStatus.Status.STOPPING,
            status_message=(reason or "Stop requested"),
            updated_at=now,
        )

        if updated:
            logger.info(
                "Stop requested for market task (task_name=%s, instance_key=%s)",
                task_name,
                key,
            )
        else:
            logger.info(
                "Stop requested for market task but no active record found "
                "(task_name=%s, instance_key=%s)",
                task_name,
                key,
            )


# Create singleton instance
task_management_handler = TaskManagementSignalHandler()

# Export convenience function
request_market_task_cancel = task_management_handler.request_market_task_cancel
handle_market_task_cancel_requested = task_management_handler.handle_market_task_cancel_requested
