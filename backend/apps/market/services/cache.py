"""Cache helpers for market metadata."""

from __future__ import annotations

from collections.abc import Iterable

from django.core.cache import cache

DEFAULT_MARKET_METADATA_CACHE_VERSION = 1


def _normalize_hostname(hostname: str) -> str:
    return hostname.replace("https://", "").replace("http://", "").strip().lower()


def _market_metadata_version_key(hostname: str) -> str:
    return f"market:metadata:version:{_normalize_hostname(hostname)}"


def get_market_metadata_cache_version(hostname: str) -> int:
    """Return the current cache namespace version for a hostname."""
    version = cache.get(_market_metadata_version_key(hostname))
    if isinstance(version, int) and version > 0:
        return version

    cache.set(
        _market_metadata_version_key(hostname),
        DEFAULT_MARKET_METADATA_CACHE_VERSION,
        timeout=None,
    )
    return DEFAULT_MARKET_METADATA_CACHE_VERSION


def build_supported_instruments_cache_key(hostname: str) -> str:
    """Build the cache key for supported instruments."""
    normalized = _normalize_hostname(hostname)
    version = get_market_metadata_cache_version(normalized)
    return f"market:supported_instruments:{normalized}:v{version}"


def build_instrument_detail_cache_key(hostname: str, instrument: str) -> str:
    """Build the cache key for instrument details."""
    normalized = _normalize_hostname(hostname)
    version = get_market_metadata_cache_version(normalized)
    return f"market:instrument_detail:{normalized}:{instrument.upper()}:v{version}"


def invalidate_market_metadata_cache(hostnames: Iterable[str]) -> None:
    """Invalidate cached market metadata for one or more hostnames."""
    for hostname in {value for value in hostnames if value}:
        normalized = _normalize_hostname(hostname)
        version_key = _market_metadata_version_key(normalized)
        current = cache.get(version_key)
        next_version = current + 1 if isinstance(current, int) and current > 0 else 2
        cache.set(version_key, next_version, timeout=None)
