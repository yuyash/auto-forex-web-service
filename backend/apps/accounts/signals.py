"""
Signal handlers for account-related events.

This module contains signal handlers for:
- Auto-creating UserSettings when a User is created
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User, UserSettings

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_settings(
    sender: type[User],  # pylint: disable=unused-argument
    instance: User,
    created: bool,
    **kwargs: object,  # pylint: disable=unused-argument
) -> None:
    """
    Auto-create UserSettings when a User is created.

    Args:
        sender: Model class (User)
        instance: User instance that was saved
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created:
        UserSettings.objects.create(user=instance)
