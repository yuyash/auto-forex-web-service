"""
Views for position management and tracking.

This module contains views for:
- Position listing directly from OANDA API
- Position detail retrieval from OANDA API
- Position closing via OANDA API

Requirements: 9.1, 9.2
"""

import logging
from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OandaAccount
from trading.oanda_api import OandaAPIClient, OandaAPIError

logger = logging.getLogger(__name__)


class PositionListView(APIView):
    """
    API endpoint for position listing directly from OANDA API.

    GET /api/positions
    - Retrieve positions directly from OANDA API
    - Filter by account, instrument, status (open/closed)

    Query Parameters:
        - account_id: OANDA account database ID (optional)
        - instrument: Currency pair (e.g., 'EUR_USD')
        - status: Position status ('open' or 'closed', default: 'open')

    Requirements: 9.1, 9.2
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """
        Retrieve positions from local database or OANDA API.

        When trading_task_id is provided, retrieves positions from the local
        database (positions created by the trading task). Otherwise, retrieves
        positions directly from OANDA API.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with position data
        """
        trading_task_id = request.query_params.get("trading_task_id")
        opened_after = request.query_params.get("opened_after")

        # If trading_task_id is provided, query local database
        if trading_task_id:
            return self._get_positions_from_database(request, trading_task_id, opened_after)

        # Otherwise, query OANDA API directly
        return self._get_positions_from_oanda(request)

    def _get_positions_from_database(
        self, request: Request, trading_task_id: str, opened_after: str | None
    ) -> Response:
        """
        Retrieve positions from local database for a trading task.

        Args:
            request: HTTP request
            trading_task_id: Trading task ID to filter by
            opened_after: ISO timestamp to filter positions opened after

        Returns:
            Response with position data from database
        """
        from django.utils.dateparse import parse_datetime

        from trading.models import Position
        from trading.trading_task_models import TradingTask

        try:
            task_id = int(trading_task_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid trading_task_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify task belongs to user
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.pk)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build query
        position_status = request.query_params.get("status", "open").lower()
        queryset = Position.objects.filter(trading_task=task)

        # Filter by status
        if position_status == "open":
            queryset = queryset.filter(closed_at__isnull=True)
        elif position_status == "closed":
            queryset = queryset.filter(closed_at__isnull=False)
        # "all" returns both open and closed

        # Filter by opened_after
        if opened_after:
            parsed_dt = parse_datetime(opened_after)
            if parsed_dt:
                queryset = queryset.filter(opened_at__gte=parsed_dt)

        # Order by opened_at descending
        queryset = queryset.order_by("-opened_at")

        # Format response to match OANDA format for frontend compatibility
        positions = []
        for pos in queryset:
            positions.append(
                {
                    "id": str(pos.position_id),
                    "instrument": pos.instrument,
                    "units": str(pos.units) if pos.direction == "long" else str(-pos.units),
                    "current_units": str(pos.units) if pos.direction == "long" else str(-pos.units),
                    "price": str(pos.entry_price),
                    "unrealized_pl": str(pos.unrealized_pnl),
                    "realized_pl": str(pos.realized_pnl) if pos.realized_pnl else "0.00",
                    "open_time": pos.opened_at.isoformat() if pos.opened_at else None,
                    "closed_time": pos.closed_at.isoformat() if pos.closed_at else None,
                    "account_name": task.oanda_account.account_id,
                    "account_db_id": task.oanda_account.id,
                    "status": "closed" if pos.closed_at else "open",
                    "direction": pos.direction,
                    "layer_number": pos.layer_number,
                    "is_first_lot": pos.is_first_lot,
                }
            )

        logger.info(
            "Positions retrieved from database for trading task",
            extra={
                "user_id": request.user.id,
                "trading_task_id": task_id,
                "status": position_status,
                "count": len(positions),
            },
        )

        return Response(
            {
                "results": positions,
                "count": len(positions),
            }
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
                accounts = [OandaAccount.objects.get(id=int(account_id), user=request.user.id)]
            except OandaAccount.DoesNotExist:
                return Response(
                    {"error": "Account not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            accounts = list(OandaAccount.objects.filter(user=request.user.id, is_active=True))

        if not accounts:
            return Response({"results": [], "count": 0})

        all_positions = []

        for account in accounts:
            try:
                client = OandaAPIClient(account)

                if position_status in ["open", "all"]:
                    # Get open trades (individual position entries)
                    trades = client.get_open_trades(instrument=instrument)
                    for trade in trades:
                        trade["account_name"] = account.account_id
                        trade["account_db_id"] = account.id
                        trade["status"] = "open"
                    all_positions.extend(trades)

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
        all_positions.sort(key=lambda x: x.get("open_time", ""), reverse=True)

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

    Requirements: 9.1, 9.2
    """

    permission_classes = [IsAuthenticated]

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
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.id)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaAPIClient(account)
            trades = client.get_open_trades()
            trade = next((t for t in trades if t.get("id") == position_id), None)

            if not trade:
                return Response(
                    {"error": "Position not found or already closed"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            trade["account_name"] = account.account_id
            trade["account_db_id"] = account.id

            logger.info(
                "Position details retrieved from OANDA",
                extra={
                    "user_id": request.user.id,
                    "position_id": position_id,
                },
            )

            return Response(trade, status=status.HTTP_200_OK)

        except OandaAPIError as e:
            logger.error("Failed to fetch position %s: %s", position_id, str(e))
            return Response(
                {"error": f"Failed to fetch position: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PositionCloseView(APIView):
    """
    API endpoint for closing positions via OANDA API.

    POST /api/positions/{trade_id}/close
    - Close a specific position at current market price
    - trade_id is the OANDA trade ID

    Request Body:
        - units: Number of units to close (optional, closes all if not provided)

    Requirements: 9.1, 9.2
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, position_id: str) -> Response:
        """
        Close a position via OANDA API.

        Args:
            request: HTTP request with optional units in body
            position_id: OANDA Trade ID

        Returns:
            Response with close transaction details
        """
        account_id = request.data.get("account_id") or request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.id)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get optional units to close
        units_str = request.data.get("units")
        units = Decimal(str(units_str)) if units_str else None

        try:
            client = OandaAPIClient(account)
            result = client.close_trade(position_id, units=units)

            logger.info(
                "Position closed via OANDA API",
                extra={
                    "user_id": request.user.id,
                    "position_id": position_id,
                    "units": str(units) if units else "ALL",
                },
            )

            return Response(
                {"message": "Position closed successfully", "details": result},
                status=status.HTTP_200_OK,
            )

        except OandaAPIError as e:
            logger.error("Failed to close position %s: %s", position_id, str(e))
            return Response(
                {"error": f"Failed to close position: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
