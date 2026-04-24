"""Shared API error response helpers for trading views."""

from __future__ import annotations

from typing import Any


def api_error(
    message: str,
    *,
    code: str,
    detail: str | None = None,
    retry_after: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Return the standard error payload used by trading APIs."""
    payload: dict[str, Any] = {
        "error": message,
        "error_code": code,
    }
    if detail:
        payload["detail"] = detail
    if retry_after is not None:
        payload["retry_after"] = retry_after
    payload.update(extra)
    return payload
