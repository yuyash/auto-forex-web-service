"""Shared utilities for account middlewares."""

from ipaddress import ip_address, ip_network
from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest
from rest_framework.request import Request

from apps.accounts.models import User


def _parse_ip(value: str) -> str | None:
    """Return a normalized IP string or ``None`` when the value is invalid."""
    raw = value.strip()
    if not raw:
        return None
    try:
        return str(ip_address(raw))
    except ValueError:
        return None


def _is_trusted_proxy(value: str) -> bool:
    """Return whether an address belongs to a configured trusted proxy CIDR."""
    parsed = _parse_ip(value)
    if parsed is None:
        return False

    candidate = ip_address(parsed)
    for raw_network in getattr(settings, "TRUSTED_PROXY_CIDRS", []):
        try:
            network = ip_network(str(raw_network), strict=False)
        except ValueError:
            continue
        if candidate in network:
            return True
    return False


def _forwarded_chain(request: HttpRequest | Request, remote_addr: str) -> list[str]:
    """Build the observed client/proxy chain for a trusted proxy request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        chain = [part.strip() for part in x_forwarded_for.split(",") if part.strip()]
    else:
        x_real_ip = request.META.get("HTTP_X_REAL_IP", "")
        chain = [x_real_ip.strip()] if x_real_ip.strip() else []

    chain.append(remote_addr)
    return chain


def get_client_ip(request: HttpRequest | Request) -> str:
    """Extract the client IP address from the request.

    Forwarded headers are trusted only when ``REMOTE_ADDR`` belongs to one of
    ``TRUSTED_PROXY_CIDRS``. The chosen address is the first untrusted hop when
    walking the forwarded chain from right to left.
    """
    remote_addr = str(request.META.get("REMOTE_ADDR", "")).strip()
    if not remote_addr:
        return "unknown"

    normalized_remote = _parse_ip(remote_addr)
    if normalized_remote is None:
        return remote_addr

    if not _is_trusted_proxy(normalized_remote):
        return normalized_remote

    for candidate in reversed(_forwarded_chain(request, normalized_remote)):
        parsed = _parse_ip(candidate)
        if parsed is not None and not _is_trusted_proxy(parsed):
            return parsed

    return normalized_remote


def get_authenticated_user(user: Any) -> User | None:
    """Return the authenticated ``User`` instance, or ``None``."""
    if user is not None and bool(getattr(user, "is_authenticated", False)):
        return cast(User, user)
    return None
