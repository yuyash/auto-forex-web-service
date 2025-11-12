"""
Signal handlers for account-related events.

This module contains signal handlers for:
- Auto-creating UserSettings when a User is created
- Starting tick data collection when default account is set
- Stopping tick data collection when default account is changed
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import OandaAccount, User, UserSettings

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


@receiver(post_save, sender=OandaAccount)
def handle_default_account_change(
    sender: type[OandaAccount],  # pylint: disable=unused-argument
    instance: OandaAccount,
    created: bool,  # pylint: disable=unused-argument
    **kwargs: object,  # pylint: disable=unused-argument
) -> None:
    """
    Handle default account changes.

    When an account is set as default:
    - Start tick data collection for the account
    - Stop tick data collection for any previous default account

    Args:
        sender: Model class (OandaAccount)
        instance: OandaAccount instance that was saved
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Only process if the account is set as default
    if not instance.is_default:
        return

    try:
        # Import here to avoid circular imports
        from trading.tasks import (  # pylint: disable=import-outside-toplevel
            collect_tick_data_for_default_account,
        )

        logger.info(
            "Default account set for user %d: %s (account_id: %s)",
            instance.user_id,
            instance.account_id,
            instance.id,
        )

        # Start tick data collection for the default account
        # This will automatically use the existing market data streaming infrastructure
        result = collect_tick_data_for_default_account.delay(user_id=instance.user_id)

        logger.info(
            "Tick data collection task started for default account %s (task: %s)",
            instance.account_id,
            result.id,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        # Log error but don't fail the save operation
        # This is especially important for tests where Celery/Redis may not be available
        logger.warning(
            "Failed to start tick data collection for default account %s: %s",
            instance.account_id,
            str(e),
        )
