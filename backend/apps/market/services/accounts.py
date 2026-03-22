"""Service helpers for OANDA account mutations."""

from __future__ import annotations

from apps.market.models import OandaAccounts
from apps.market.serializers import OandaAccountsSerializer


def create_oanda_account(serializer: OandaAccountsSerializer) -> OandaAccounts:
    """Persist a new OANDA account from a validated serializer."""
    return serializer.save()


def update_oanda_account(serializer: OandaAccountsSerializer) -> OandaAccounts:
    """Persist OANDA account updates from a validated serializer."""
    return serializer.save()


def delete_oanda_account(account: OandaAccounts) -> None:
    """Delete an OANDA account through a shared mutation path."""
    account.delete()
