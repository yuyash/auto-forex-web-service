"""Standardised API error response helpers."""

from __future__ import annotations

from typing import Any

from rest_framework.response import Response


def error_response(
    error: str,
    detail: str | None = None,
    *,
    status_code: int = 400,
    extras: dict[str, Any] | None = None,
) -> Response:
    """Return a consistently shaped error ``Response``.

    Every error body contains at least ``{"error": "..."}`` and optionally
    ``{"detail": "..."}`` plus any additional keys supplied via *extras*.
    """
    body: dict[str, Any] = {"error": error}
    if detail is not None:
        body["detail"] = detail
    if extras:
        body.update(extras)
    return Response(body, status=status_code)
