"""Helpers for bounded upstream list fan-out."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

from django.conf import settings

from apps.market.models import OandaAccounts
from apps.market.services.oanda import OandaAPIError

T = TypeVar("T")


def upstream_history_count(*, page: int, page_size: int) -> int:
    """Return a bounded upstream history count for paginated API views."""
    default_count = int(getattr(settings, "OANDA_LIST_DEFAULT_HISTORY_COUNT", 200))
    max_count = int(getattr(settings, "OANDA_LIST_MAX_HISTORY_COUNT", 500))
    requested_count = max(page, 1) * max(page_size, 1)
    return min(max(requested_count * 2, default_count), max_count)


def fetch_account_lists(
    accounts: Sequence[OandaAccounts],
    fetcher: Callable[[OandaAccounts], list[T]],
) -> tuple[list[T], list[str]]:
    """Fetch upstream list payloads for accounts with bounded parallelism."""
    if not accounts:
        return [], []

    max_workers = max(int(getattr(settings, "OANDA_LIST_MAX_WORKERS", 4)), 1)
    workers = min(max_workers, len(accounts))
    results: list[T] = []
    failed_accounts: list[str] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_account = {executor.submit(fetcher, account): account for account in accounts}
        for future in as_completed(future_to_account):
            account = future_to_account[future]
            try:
                results.extend(future.result())
            except OandaAPIError:
                failed_accounts.append(str(account.account_id))

    return results, failed_accounts
