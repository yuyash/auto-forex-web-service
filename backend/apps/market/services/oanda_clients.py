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

    def get_details(self):
        """Fetch normalized account details."""
        return self.service._get_account_details_impl()

    def get_hedging_enabled(self) -> bool:
        """Return whether account hedging mode is enabled."""
        return self.service._get_account_hedging_enabled_impl()

    def get_position_mode(self) -> str:
        """Return the account's position mode."""
        return self.service._get_account_position_mode_impl()


class OandaOrderClient:
    """Order submission and lookup client."""

    def __init__(self, service: Any) -> None:
        """Bind this collaborator to an initialized OandaService instance."""
        self.service = service

    def cancel_order(self, order: Any):
        """Cancel an existing broker order."""
        return self.service._cancel_order_impl(order)

    def create_limit_order(self, request: Any):
        """Create a pending limit order."""
        return self.service._create_limit_order_impl(request)

    def create_market_order(self, request: Any, override_price: Any = None):
        """Create a market order."""
        return self.service._create_market_order_impl(request, override_price=override_price)

    def create_stop_order(self, request: Any):
        """Create a pending stop order."""
        return self.service._create_stop_order_impl(request)

    def create_oco_order(self, request: Any):
        """Create an OCO order from limit and stop legs."""
        return self.service._create_oco_order_impl(request)

    def get_pending_orders(self, instrument: str | None = None):
        """Fetch pending broker orders."""
        return self.service._get_pending_orders_impl(instrument=instrument)

    def get_order_history(
        self,
        instrument: str | None = None,
        count: int = 50,
        state: str = "ALL",
    ):
        """Fetch broker order history."""
        return self.service._get_order_history_impl(
            instrument=instrument,
            count=count,
            state=state,
        )

    def get_order(self, order_id: str):
        """Fetch one broker order by id."""
        return self.service._get_order_impl(order_id)


class OandaTradeClient:
    """Trade close and history client."""

    def __init__(self, service: Any) -> None:
        """Bind this collaborator to an initialized OandaService instance."""
        self.service = service

    def close_trade(self, trade: Any, units: Any = None):
        """Close an individual broker trade."""
        return self.service._close_trade_impl(trade=trade, units=units)

    def get_trades(
        self,
        instrument: str | None = None,
        *,
        state: str = "OPEN",
        count: int = 500,
    ):
        """Fetch broker trades by state."""
        return self.service._get_trades_impl(
            instrument=instrument,
            state=state,
            count=count,
        )

    def get_open_trades(self, instrument: str | None = None):
        """Fetch currently open broker trades."""
        return self.service._get_open_trades_impl(instrument=instrument)


class OandaPositionClient:
    """Position close and lookup client."""

    def __init__(self, service: Any) -> None:
        """Bind this collaborator to an initialized OandaService instance."""
        self.service = service

    def close_position(self, position: Any, units: Any = None, override_price: Any = None):
        """Close a broker position by instrument exposure."""
        return self.service._close_position_impl(
            position=position,
            units=units,
            override_price=override_price,
        )

    def get_open_positions(self, instrument: str | None = None):
        """Fetch open broker positions."""
        return self.service._get_open_positions_impl(instrument=instrument)


class OandaTransactionClient:
    """Transaction-history client."""

    def __init__(self, service: Any) -> None:
        """Bind this collaborator to an initialized OandaService instance."""
        self.service = service

    def get_transaction_history(
        self,
        *,
        from_time: Any = None,
        to_time: Any = None,
        page_size: int = 100,
        transaction_type: str | None = None,
    ):
        """Fetch account transaction history."""
        return self.service._get_transaction_history_impl(
            from_time=from_time,
            to_time=to_time,
            page_size=page_size,
            transaction_type=transaction_type,
        )


class OandaPricingStreamClient:
    """Pricing stream client."""

    def __init__(self, service: Any) -> None:
        """Bind this collaborator to an initialized OandaService instance."""
        self.service = service

    def stream_pricing_ticks(
        self,
        instruments: list[str] | str,
        *,
        snapshot: bool = True,
        include_heartbeats: bool = False,
    ):
        """Stream pricing ticks from OANDA."""
        return self.service._stream_pricing_ticks_impl(
            instruments,
            snapshot=snapshot,
            include_heartbeats=include_heartbeats,
        )
