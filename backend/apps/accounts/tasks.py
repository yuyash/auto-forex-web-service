"""Celery tasks for the accounts app."""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="accounts.tasks.cleanup_expired_refresh_tokens")
def cleanup_expired_refresh_tokens() -> int:
    """Delete refresh tokens that are expired or revoked.

    Scheduled via Celery Beat to prevent unbounded table growth.
    Returns the number of deleted rows.
    """
    from apps.accounts.models import RefreshToken

    now = timezone.now()
    qs = RefreshToken.objects.filter(
        # Expired OR revoked
        models_q_expired_or_revoked(now),
    )
    count, _ = qs.delete()
    if count:
        logger.info("Cleaned up %d expired/revoked refresh tokens", count)
    return count


def models_q_expired_or_revoked(now):  # noqa: ANN001
    """Build a Q filter for tokens that are safe to delete."""
    from django.db.models import Q

    return Q(expires_at__lt=now) | Q(revoked_at__isnull=False)
