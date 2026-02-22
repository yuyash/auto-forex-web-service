"""
Signal handlers for account-related events.

This module contains signal handlers for:
- Auto-creating UserSettings when a User is created
"""

from logging import Logger, getLogger

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User, UserSettings

logger: Logger = getLogger(name=__name__)


@receiver(signal=post_save, sender=User)
def create_user_settings(
    sender: type[User],
    instance: User,
    created: bool,
    **kwargs: object,
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
        logger.info(
            "Signal received: Creating UserSettings for user '%s' (email: %s, id: %s)",
            instance.username,
            instance.email,
            instance.pk,
        )
        UserSettings.objects.create(user=instance)
    else:
        logger.debug(
            "Signal received: User '%s' (email: %s, id: %s) was updated",
            instance.username,
            instance.email,
            instance.pk,
        )
