"""
Signal handlers for accounts app.

This module contains signal handlers for:
- Updating active strategies when user settings change

Requirements: 29.5
"""

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User, UserSettings

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def update_strategies_on_user_change(
    sender: type[User],  # pylint: disable=unused-argument
    instance: User,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Update active strategies when user profile changes.

    This handler is triggered when a User instance is saved.
    It logs that user settings have changed so that active strategies
    can pick up the new timezone or language settings on the next tick.

    Args:
        sender: The model class (User)
        instance: The User instance that was saved
        created: Whether this is a new instance
        kwargs: Additional keyword arguments

    Requirements: 29.5
    """
    # Skip if this is a new user
    if created:
        return

    try:
        from trading.models import Strategy  # pylint: disable=import-outside-toplevel

        # Get all active strategies for this user's accounts
        active_strategies = Strategy.objects.filter(
            account__user=instance,
            is_active=True,
        )

        if active_strategies.exists():
            logger.info(
                "User settings changed for %s with %s active strategies",
                instance.email,
                active_strategies.count(),
                extra={
                    "user_id": instance.id,
                    "email": instance.email,
                    "strategy_count": active_strategies.count(),
                    "timezone": instance.timezone,
                    "language": instance.language,
                },
            )

            # Note: The actual strategy update logic will be handled by the
            # strategy executor when it processes the next tick.
            # Timezone and language changes don't require immediate strategy updates.

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to check strategies for user %s: %s",
            instance.email,
            str(exc),
            extra={
                "user_id": instance.id,
                "email": instance.email,
                "error": str(exc),
            },
            exc_info=True,
        )


@receiver(post_save, sender=UserSettings)
def update_strategies_on_settings_change(
    sender: type[UserSettings],  # pylint: disable=unused-argument
    instance: UserSettings,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Update active strategies when user settings change.

    This handler is triggered when a UserSettings instance is saved.
    It updates the configuration of all active strategies for the user
    to reflect the new strategy defaults.

    Args:
        sender: The model class (UserSettings)
        instance: The UserSettings instance that was saved
        created: Whether this is a new instance
        kwargs: Additional keyword arguments

    Requirements: 29.5
    """
    # Skip if this is a new settings instance
    if created:
        return

    try:
        from trading.models import Strategy  # pylint: disable=import-outside-toplevel

        # Get all active strategies for this user's accounts
        active_strategies = Strategy.objects.filter(
            account__user=instance.user,
            is_active=True,
        )

        if active_strategies.exists():
            logger.info(
                "Updating %s active strategies for user %s due to settings change",
                active_strategies.count(),
                instance.user.email,
                extra={
                    "user_id": instance.user.id,
                    "email": instance.user.email,
                    "strategy_count": active_strategies.count(),
                },
            )

            # Update each strategy's config with new defaults
            for strategy in active_strategies:
                config = strategy.config or {}

                # Update config with new defaults (only if not explicitly set)
                if "lot_size" not in config:
                    config["lot_size"] = float(instance.default_lot_size)

                if "scaling_mode" not in config:
                    config["scaling_mode"] = instance.default_scaling_mode

                if "retracement_pips" not in config:
                    config["retracement_pips"] = instance.default_retracement_pips

                if "take_profit_pips" not in config:
                    config["take_profit_pips"] = instance.default_take_profit_pips

                strategy.update_config(config)

            logger.info(
                "Successfully updated %s active strategies for user %s",
                active_strategies.count(),
                instance.user.email,
                extra={
                    "user_id": instance.user.id,
                    "email": instance.user.email,
                    "strategy_count": active_strategies.count(),
                },
            )

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to update strategies for user %s: %s",
            instance.user.email,
            str(exc),
            extra={
                "user_id": instance.user.id,
                "email": instance.user.email,
                "error": str(exc),
            },
            exc_info=True,
        )
