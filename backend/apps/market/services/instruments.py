from __future__ import annotations

from decimal import Decimal
from typing import Any

import v20
from django.core.cache import cache

from apps.market.models import OandaAccount


def get_pip_size(*, instrument: str) -> Decimal:
    """Return pip size for an instrument using OANDA instrument metadata.

    This intentionally does not guess based on the instrument name.
    For FX pairs, OANDA provides `pipLocation` which implies pip size as:
        pip_size = 10 ** pipLocation
    """

    instrument_norm = str(instrument).strip().upper()
    if not instrument_norm:
        raise ValueError("instrument is required")

    cache_key = f"market:pip_size:{instrument_norm}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Decimal(str(cached))

    account = OandaAccount.objects.filter(is_active=True).first()
    if not account:
        raise ValueError("No active OANDA account found for pip size lookup")

    api = v20.Context(
        hostname=account.api_hostname,
        token=account.get_api_token(),
        poll_timeout=10,
    )

    response: Any = api.account.instruments(account.account_id, instruments=instrument_norm)
    if int(getattr(response, "status", 0)) != 200:
        raise ValueError(
            f"OANDA API error fetching instruments: {getattr(response, 'status', None)}"
        )

    instruments_list = (getattr(response, "body", None) or {}).get("instruments", [])
    if not instruments_list:
        raise ValueError(f"Instrument not found: {instrument_norm}")

    instr = instruments_list[0]
    pip_location = int(instr.pipLocation)
    pip_size = Decimal("10") ** pip_location

    cache.set(cache_key, str(pip_size), timeout=24 * 60 * 60)
    return pip_size
