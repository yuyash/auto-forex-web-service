"""Account-related signal handlers."""

from __future__ import annotations

from logging import Logger, getLogger

from django.db import transaction
from django.db.models.signals import post_save

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.signals.base import SignalHandler

logger: Logger = getLogger(name=__name__)


class AccountSignalHandler(SignalHandler):
    """Handler for account-related signals."""

    def connect(self) -> None:
        """Connect account signal handlers."""
        post_save.connect(
            self.bootstrap_tick_pubsub_on_first_live_account,
            sender=OandaAccounts,
            dispatch_uid="market.signals.bootstrap_tick_pubsub_on_first_live_account",
        )

    def bootstrap_tick_pubsub_on_first_live_account(
        self,
        sender: type[OandaAccounts],
        instance: OandaAccounts,
        created: bool,
        **_kwargs: object,
    ) -> None:
        """Bootstrap tick pub/sub system when first LIVE account is created.

        Args:
            sender: OandaAccounts model class
            instance: The created/updated account instance
            created: Whether this is a new instance
        """
        _ = sender

        # Only trigger on account creation
        if not created:
            return

        # Only trigger for LIVE accounts
        if instance.api_type != ApiType.LIVE:
            return

        # Only trigger for the first LIVE account
        live_count = OandaAccounts.objects.filter(api_type=ApiType.LIVE).count()
        if live_count != 1:
            return

        def _start_tasks() -> None:
            """Start tick pub/sub tasks after transaction commits."""
            try:
                logger.info(
                    "First live OANDA account created; bootstrapping tick pub/sub (account_id=%s)",
                    instance.id,  # type: ignore[attr-defined]
                )

                from apps.market.tasks import ensure_tick_pubsub_running

                ensure_tick_pubsub_running.delay()

            except Exception as exc:
                logger.exception("Failed to bootstrap tick pub/sub tasks: %s", exc)

        transaction.on_commit(_start_tasks)


# Create singleton instance
account_handler = AccountSignalHandler()

# Export convenience function
bootstrap_tick_pubsub_on_first_live_account = (
    account_handler.bootstrap_tick_pubsub_on_first_live_account
)
