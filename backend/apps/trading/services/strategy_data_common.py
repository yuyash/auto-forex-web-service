"""Shared query and serialization helpers for strategy data endpoints."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request


DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 5000


@dataclass(frozen=True)
class StrategyDataQuery:
    execution_id: Any
    since: datetime | None
    until: datetime | None
    page: int
    page_size: int
    ordering: str
    granularity: str
    category: str
    metric_keys: tuple[str, ...]


def page_rows(
    *, request: Request, rows: list[dict[str, Any]], query: StrategyDataQuery
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total = len(rows)
    start = (query.page - 1) * query.page_size
    results = rows[start : start + query.page_size]
    return results, {
        "count": total,
        "next": _page_url(request, query.page + 1, total, query.page_size),
        "previous": _page_url(request, query.page - 1, total, query.page_size),
        "page": query.page,
        "page_size": query.page_size,
        "ordering": query.ordering,
        "granularity": query.granularity,
    }


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"Invalid datetime: {value}") from exc
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def normalise_granularity(value: str | None) -> str:
    """Normalise a granularity string to an OANDA-compatible token.

    Accepts ``raw``/``tick``/``1`` as the tick-level sentinel, a bare integer
    interpreted as a minute count (``"240"`` -> ``"M240"``), or OANDA-style
    tokens ``M{n}``, ``H{n}``, ``D``, ``W`` and ``MO`` (month). The trailing
    ``MO`` alias exists because bare ``M`` collides with the minute prefix.
    """

    raw = str(value or "raw").strip().upper()
    if raw in {"", "RAW", "TICK", "1"}:
        return "raw"
    if raw.isdigit():
        return f"M{raw}"
    if raw in {"D", "W", "MO"}:
        return raw
    if len(raw) >= 2 and raw[0] in {"M", "H"} and raw[1:].isdigit():
        minutes = int(raw[1:]) * (60 if raw[0] == "H" else 1)
        if minutes >= 1:
            return f"M{minutes}" if raw[0] == "H" else raw
    raise ValidationError(
        "granularity must be raw, tick, a positive minute count, or an "
        "OANDA-style token such as M1, M5, M15, H1, H4, D, W, or MO."
    )


def granularity_seconds(value: str) -> int | None:
    """Convert a normalised granularity token to seconds (``None`` for ``raw``)."""

    if value == "raw":
        return None
    if value.startswith("M") and value[1:].isdigit():
        return int(value[1:]) * 60
    if value.startswith("H") and value[1:].isdigit():
        return int(value[1:]) * 3600
    return {"D": 86400, "W": 604800, "MO": 2592000}.get(value)


def positive_int(value: str | None, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Expected a positive integer.") from exc
    if parsed < 1:
        raise ValidationError("Expected a positive integer.")
    return parsed


def float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value) if hasattr(value, "hex") and callable(value.hex) else value


def string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _page_url(request: Request, page: int, total: int, page_size: int) -> str | None:
    total_pages = math.ceil(total / page_size) if page_size else 1
    if page < 1 or page > total_pages:
        return None
    params = request.query_params.copy()
    params["page"] = str(page)
    params["page_size"] = str(page_size)
    return f"{request.build_absolute_uri(request.path)}?{urlencode(params, doseq=True)}"
