"""Focused OANDA client collaborators used by the high-level service."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import Any

import v20
from django.conf import settings

from apps.market.services.oanda_types import OandaAPIError

logger: Logger = getLogger(name=__name__)


class OandaContextFactory:
    """Factory for REST and stream v20 contexts."""

    def __init__(self, *, v20_module: Any = v20, settings_module: Any = settings) -> None:
        """Initialize with patchable v20/settings dependencies."""
        self.v20_module = v20_module
        self.settings_module = settings_module

    @staticmethod
    def stream_hostname(hostname: str) -> str:
        """Return the stream hostname matching an OANDA REST hostname."""
        host = (hostname or "").strip()
        if not host:
            return host
        if host.startswith("stream-"):
            return host
        if host.startswith("api-"):
            return "stream-" + host[len("api-") :]
        return host

    def create_rest_context(self, account: Any) -> v20.Context:
        """Create a REST API context for an account."""
        return self.v20_module.Context(
            hostname=str(account.api_hostname),
            token=account.get_api_token(),
            poll_timeout=10,
        )

    def create_stream_context(self, account: Any) -> v20.Context:
        """Create a streaming API context for an account."""
        return self.v20_module.Context(
            hostname=self.stream_hostname(str(account.api_hostname)),
            token=account.get_api_token(),
            stream_timeout=int(getattr(self.settings_module, "OANDA_STREAM_TIMEOUT", 30)),
            poll_timeout=10,
        )


class OandaAccountClient:
    """Account-resource client with per-service response caching."""

    def __init__(self, service: Any) -> None:
        """Bind this collaborator to an initialized OandaService instance."""
        self.service = service

    def get_resource(self, *, refresh: bool = False) -> dict[str, Any]:
        """Fetch the raw OANDA account resource as a dictionary."""
        service = self.service
        assert service.api is not None, "API client not initialized"
        assert service.account is not None, "Account not initialized"

        if not refresh and service._account_resource_cache is not None:
            return service._account_resource_cache

        try:
            response = service.api.account.get(service.account.account_id)
            if response.status != 200:
                raise OandaAPIError(f"Failed to fetch account resource: status {response.status}")

            body = getattr(response, "body", {})
            if hasattr(body, "get"):
                account_data = body.get("account")
            else:
                account_data = getattr(body, "account", None)

            account_resource = service._account_object_to_dict(account_data)
            service._account_resource_cache = account_resource
            return account_resource
        except OandaAPIError:
            raise
        except Exception as e:
            account_id = service.account.account_id if service.account else "unknown"
            logger.error(
                "Error fetching account resource for %s",
                account_id,
                exc_info=True,
            )
            raise OandaAPIError(
                "Error fetching account resource",
                internal_detail=str(e),
            ) from e
