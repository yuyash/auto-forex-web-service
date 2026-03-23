"""Shared account resolution helpers for market views."""

from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.market.models import OandaAccounts


def get_user_accounts(
    request: Request,
    account_id: str | int | None = None,
    *,
    active_only: bool = True,
) -> tuple[list[OandaAccounts], Response | None]:
    """Resolve OANDA accounts for the authenticated user.

    Returns a ``(accounts, error_response)`` tuple.  When *error_response*
    is not ``None`` the caller should return it directly.
    """
    if account_id:
        try:
            account = OandaAccounts.objects.get(id=int(account_id), user=request.user.pk)
            return [account], None
        except (ValueError, TypeError):
            return [], Response(
                {"error": "Invalid account_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OandaAccounts.DoesNotExist:
            return [], Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

    qs = OandaAccounts.objects.filter(user=request.user.pk)
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs), None


def get_user_default_account(request: Request) -> tuple[OandaAccounts | None, Response | None]:
    """Return the user's default (or first) active OANDA account.

    Returns ``(account, error_response)``.  When *error_response* is not
    ``None`` the caller should return it directly.
    """
    user_id = request.user.pk
    account = (
        OandaAccounts.objects.filter(user_id=user_id, is_active=True, is_default=True).first()
        or OandaAccounts.objects.filter(user_id=user_id, is_active=True).first()
    )
    if account is None:
        return None, Response(
            {
                "error": "No OANDA account found. Please configure an account first.",
                "error_code": "NO_OANDA_ACCOUNT",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return account, None
