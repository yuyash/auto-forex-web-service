"""Position views."""

from decimal import Decimal
from logging import Logger, getLogger

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts
from apps.market.serializers import PositionSerializer
from apps.market.services.compliance import ComplianceViolationError
from apps.market.services.oanda import (
    MarketOrderRequest,
    OandaAPIError,
    OandaService,
    OpenTrade,
)

logger: Logger = getLogger(name=__name__)


class PositionView(APIView):
    """
    API endpoint for position listing directly from OANDA API.

    GET /api/market/positions/
    - Retrieve positions directly from OANDA API
    - Filter by account, instrument, status (open/closed)

    PUT /api/market/positions/
    - Open a new position by submitting a market order via OANDA

    Query Parameters:
        - account_id: OANDA account database ID (optional)
        - instrument: Currency pair (e.g., 'EUR_USD')
        - status: Position status ('open' or 'closed', default: 'open')
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="GET /api/market/positions/",
        description="Retrieve positions directly from OANDA API",
        operation_id="list_positions",
        tags=["Market - Positions"],
        parameters=[
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="OANDA account database ID",
            ),
            OpenApiParameter(
                name="instrument",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Currency pair filter",
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Position status (open/closed/all)",
                default="open",
            ),
        ],
        responses={200: dict},
    )
    def get(self, request: Request) -> Response:
        """
        Retrieve positions directly from OANDA API.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with position data
        """
        return self._get_positions_from_oanda(request)

    @extend_schema(
        summary="PUT /api/market/positions/",
        description="Open a new position by submitting a market order via OANDA",
        operation_id="open_position",
        tags=["Market - Positions"],
        request=PositionSerializer,
        responses={201: dict},
    )
    def put(self, request: Request) -> Response:
        """
        Open a new position via OANDA by submitting a market order.

        Body:
            - account_id: OANDA account database ID (required)
            - instrument: Currency pair (e.g., 'EUR_USD') (required)
            - direction: 'long' or 'short' (required)
            - units: number of units (required)
            - take_profit: optional TP price
            - stop_loss: optional SL price

        Returns:
            Response with created order details
        """

        serializer = PositionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        account_id = request.data.get("account_id")
        if not account_id:
            return Response({"error": "account_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = OandaAccounts.objects.get(id=int(account_id), user=request.user.pk)
        except (ValueError, TypeError, OandaAccounts.DoesNotExist):
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        validated = serializer.validated_data
        instrument = validated["instrument"]
        direction = validated["direction"]
        units = validated["units"]
        take_profit = validated.get("take_profit")
        stop_loss = validated.get("stop_loss")

        signed_units = units if direction == "long" else -units

        try:
            client = OandaService(account)
            result = client.create_market_order(
                MarketOrderRequest(
                    instrument=instrument,
                    units=signed_units,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            )

            return Response(
                {
                    "id": result.order_id,
                    "instrument": result.instrument,
                    "type": result.order_type.value,
                    "units": str(result.units),
                    "price": str(result.price) if result.price is not None else None,
                    "state": result.state.value,
                    "create_time": result.create_time.isoformat() if result.create_time else None,
                    "account_name": account.account_id,
                    "account_db_id": account.pk,
                },
                status=status.HTTP_201_CREATED,
            )
        except (OandaAPIError, ComplianceViolationError) as e:
            logger.error("Position open (market order) failed: %s", e)
            return Response(
                {"error": f"Order execution failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error opening position: %s", e)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_positions_from_oanda(self, request: Request) -> Response:
        """
        Retrieve positions directly from OANDA API.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with position data from OANDA
        """
        account_id = request.query_params.get("account_id")
        instrument = request.query_params.get("instrument")
        position_status = request.query_params.get("status", "open").lower()

        # Validate status parameter
        if position_status not in ["open", "closed", "all"]:
            return Response(
                {"error": "Invalid status. Must be 'open', 'closed', or 'all'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get accounts to query
        if account_id:
            try:
                accounts = [OandaAccounts.objects.get(id=int(account_id), user=request.user.id)]
            except OandaAccounts.DoesNotExist:
                return Response(
                    {"error": "Account not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            accounts = list(OandaAccounts.objects.filter(user=request.user.id, is_active=True))

        if not accounts:
            return Response({"results": [], "count": 0})

        all_positions = []

        for account in accounts:
            try:
                client = OandaService(account)

                if position_status in ["open", "all"]:
                    # Get open trades (individual position entries)
                    trades = client.get_open_trades(instrument=instrument)
                    for trade in trades:
                        all_positions.append(
                            {
                                "id": trade.trade_id,
                                "instrument": trade.instrument,
                                "direction": trade.direction.value,
                                "units": str(trade.units),
                                "entry_price": str(trade.entry_price),
                                "unrealized_pnl": str(trade.unrealized_pnl),
                                "open_time": (
                                    trade.open_time.isoformat() if trade.open_time else None
                                ),
                                "state": trade.state,
                                "account_name": account.account_id,
                                "account_db_id": account.pk,
                                "status": "open",
                            }
                        )

                # Note: OANDA doesn't provide a direct "closed positions" API
                # Closed positions must be retrieved from transaction history
                # For now, we only show open positions from OANDA

            except OandaAPIError as e:
                logger.error(
                    "Failed to fetch positions from OANDA for account %s: %s",
                    account.account_id,
                    str(e),
                )
                # Continue with other accounts

        # Sort by open time (newest first)
        all_positions.sort(key=lambda x: str(x.get("open_time") or ""), reverse=True)

        logger.info(
            "Positions retrieved from OANDA",
            extra={
                "user_id": request.user.id,
                "account_id": account_id,
                "instrument": instrument,
                "status": position_status,
                "count": len(all_positions),
            },
        )

        return Response(
            {
                "results": all_positions,
                "count": len(all_positions),
            }
        )


class PositionDetailView(APIView):
    """
    API endpoint for position detail retrieval from OANDA API.

    GET /api/positions/{trade_id}
    - Retrieve detailed information for a specific trade/position from OANDA
    - trade_id is the OANDA trade ID
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="GET /api/market/positions/{position_id}/",
        description="Retrieve detailed information for a specific trade/position from OANDA",
        operation_id="get_position_detail",
        tags=["Market - Positions"],
        parameters=[
            OpenApiParameter(
                name="position_id",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="OANDA Trade ID",
            ),
            OpenApiParameter(
                name="account_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description="OANDA account database ID",
            ),
        ],
        responses={200: dict},
    )
    def get(self, request: Request, position_id: str) -> Response:
        """
        Retrieve position details from OANDA API.

        Args:
            request: HTTP request
            position_id: OANDA Trade ID

        Returns:
            Response with position data from OANDA
        """
        account_id = request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccounts.objects.get(id=int(account_id), user=request.user.pk)
        except OandaAccounts.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaService(account)
            trades = client.get_open_trades()
            trade: OpenTrade | None = next((t for t in trades if t.trade_id == position_id), None)

            if not trade:
                return Response(
                    {"error": "Position not found or already closed"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            trade_data = {
                "id": trade.trade_id,
                "instrument": trade.instrument,
                "direction": trade.direction.value,
                "units": str(trade.units),
                "entry_price": str(trade.entry_price),
                "unrealized_pnl": str(trade.unrealized_pnl),
                "open_time": trade.open_time.isoformat() if trade.open_time else None,
                "state": trade.state,
                "account_name": account.account_id,
                "account_db_id": account.pk,
            }

            logger.info(
                "Position details retrieved from OANDA",
                extra={
                    "user_id": request.user.id,
                    "position_id": position_id,
                },
            )

            return Response(trade_data, status=status.HTTP_200_OK)

        except OandaAPIError as e:
            logger.error("Failed to fetch position %s: %s", position_id, str(e))
            return Response(
                {"error": f"Failed to fetch position: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="PATCH /api/market/positions/{position_id}/",
        description="Close a position via OANDA API",
        operation_id="close_position",
        tags=["Market - Positions"],
        parameters=[
            OpenApiParameter(
                name="position_id",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="OANDA Trade ID",
            ),
        ],
        request=dict,
        responses={200: dict},
    )
    def patch(self, request: Request, position_id: str) -> Response:
        """
        Close a position via OANDA API.

        PATCH /api/positions/{trade_id}

        Body (optional):
            - account_id: OANDA account database ID (required)
            - units: Number of units to close (optional, closes all if not provided)
        """
        account_id = request.data.get("account_id") or request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccounts.objects.get(id=int(account_id), user=request.user.id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid account_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OandaAccounts.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        units_str = request.data.get("units")
        units = Decimal(str(units_str)) if units_str else None

        try:
            client = OandaService(account)
            trades = client.get_open_trades()
            trade = next((t for t in trades if t.trade_id == position_id), None)
            if not trade:
                return Response(
                    {"error": "Position not found or already closed"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            result = client.close_trade(trade, units=units)

            logger.info(
                "Position closed via OANDA API",
                extra={
                    "user_id": request.user.id,
                    "position_id": position_id,
                    "units": str(units) if units else "ALL",
                },
            )

            return Response(
                {
                    "message": "Position closed successfully",
                    "details": {
                        "id": result.order_id,
                        "instrument": result.instrument,
                        "type": result.order_type.value,
                        "direction": result.direction.value,
                        "units": str(result.units),
                        "price": str(result.price) if result.price is not None else None,
                        "state": result.state.value,
                        "fill_time": result.fill_time.isoformat() if result.fill_time else None,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except OandaAPIError as e:
            logger.error("Failed to close position %s: %s", position_id, str(e))
            return Response(
                {"error": f"Failed to close position: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
