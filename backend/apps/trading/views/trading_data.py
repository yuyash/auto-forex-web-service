"""Views for TradingTask data endpoints."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.models import TradingTasks
from apps.trading.services.equity import EquityService
from apps.trading.services.performance import LivePerformanceService
from apps.trading.views._helpers import (
    _get_execution_metrics_or_none,
    _paginate_list_by_page,
    _paginate_queryset_by_page,
)


class TradingTaskResultsView(APIView):
    """Unified results endpoint for a trading task.

    Returns live Redis snapshot when running and latest execution metrics when available.
    Equity curve is downsampled so the returned point count does not exceed 500.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTasks.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTasks.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        execution_payload = None
        metrics_payload = None

        if latest_execution:
            execution_payload = {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "progress": latest_execution.progress,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "error_message": latest_execution.error_message or None,
            }

            metrics_obj = _get_execution_metrics_or_none(latest_execution)
            if metrics_obj:
                # TODO: Update to use TradingMetrics model
                metrics_payload = {}

        live = LivePerformanceService.get_trading_intermediate_results(task_id)
        has_live = live is not None
        has_metrics = metrics_payload is not None

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "has_live": has_live,
                "live": live,
                "has_metrics": has_metrics,
                "metrics": metrics_payload,
                "execution": execution_payload,
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskEquityCurveView(APIView):
    """Equity curve for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTasks.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTasks.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_metrics": False,
                    "equity_curve": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "equity_curve_granularity_seconds": None,
                },
                status=status.HTTP_200_OK,
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        # TODO: This endpoint will be replaced by execution-based endpoints
        # The old ExecutionEquityPoint model has been removed
        # Use the new TradingMetrics model with granularity aggregation instead
        if not metrics_obj:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": latest_execution.pk,
                    "has_metrics": False,
                    "equity_curve": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                    "equity_curve_granularity_seconds": None,
                },
                status=status.HTTP_200_OK,
            )

        equity_service = EquityService()
        ds = equity_service.downsample_equity_curve(
            metrics_obj.equity_curve,
            max_points=500,
            start_dt=latest_execution.started_at,
            end_dt=latest_execution.completed_at,
        )

        pagination = _paginate_list_by_page(
            request=request,
            items=list(ds.points),
            base_url=f"/api/trading/trading-tasks/{task_id}/equity-curve/",
            default_page_size=500,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_metrics": True,
                "equity_curve": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
                "equity_curve_granularity_seconds": ds.granularity_seconds,
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskStrategyEventsView(APIView):
    """Strategy events for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTasks.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTasks.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_metrics": False,
                    "strategy_events": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                },
                status=status.HTTP_200_OK,
            )

        from apps.trading.models import StrategyEvents

        qs = (
            StrategyEvents.objects.filter(execution=latest_execution)
            .order_by("sequence", "id")
            .values_list("event", flat=True)
        )

        pagination = _paginate_queryset_by_page(
            request=request,
            queryset=qs,
            base_url=f"/api/trading/trading-tasks/{task_id}/strategy-events/",
            default_page_size=1000,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_metrics": pagination["count"] > 0,
                "strategy_events": list(pagination["results"]),
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskTradeLogsView(APIView):
    """Trade logs for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTasks.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTasks.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_metrics": False,
                    "trade_logs": [],
                    "count": 0,
                    "next": None,
                    "previous": None,
                },
                status=status.HTTP_200_OK,
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        # Live fallback (DB-backed incremental trades)
        if not metrics_obj:
            from apps.trading.models import TradeLogs

            qs = (
                TradeLogs.objects.filter(execution=latest_execution)
                .order_by("sequence", "id")
                .values_list("trade", flat=True)
            )

            pagination = _paginate_queryset_by_page(
                request=request,
                queryset=qs,
                base_url=f"/api/trading/trading-tasks/{task_id}/trade-logs/",
                default_page_size=1000,
                max_page_size=1000,
            )

            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": latest_execution.pk,
                    "has_metrics": pagination["count"] > 0,
                    "trade_logs": pagination["results"],
                    "count": pagination["count"],
                    "next": pagination["next"],
                    "previous": pagination["previous"],
                },
                status=status.HTTP_200_OK,
            )

        trades = metrics_obj.trade_log if isinstance(metrics_obj.trade_log, list) else []

        pagination = _paginate_list_by_page(
            request=request,
            items=list(trades),
            base_url=f"/api/trading/trading-tasks/{task_id}/trade-logs/",
            default_page_size=1000,
            max_page_size=1000,
        )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_metrics": True,
                "trade_logs": pagination["results"],
                "count": pagination["count"],
                "next": pagination["next"],
                "previous": pagination["previous"],
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskMetricsCheckpointView(APIView):
    """Latest metrics checkpoint for the latest trading execution."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        try:
            task = TradingTasks.objects.select_related("config", "user", "oanda_account").get(
                id=task_id, user=request.user.pk
            )
        except TradingTasks.DoesNotExist:
            return Response({"error": "Trading task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": None,
                    "has_checkpoint": False,
                    "checkpoint": None,
                },
                status=status.HTTP_200_OK,
            )

        # TODO: Update to use TradingMetrics model
        checkpoint = None

        if not checkpoint:
            return Response(
                {
                    "task_id": task_id,
                    "task_type": "trading",
                    "execution_id": latest_execution.pk,
                    "has_checkpoint": False,
                    "checkpoint": None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "task_id": task_id,
                "task_type": "trading",
                "execution_id": latest_execution.pk,
                "has_checkpoint": True,
                "checkpoint": {
                    "id": checkpoint.pk,
                    "execution_id": latest_execution.pk,
                    "processed": checkpoint.processed,
                    "total_return": str(checkpoint.total_return),
                    "total_pnl": str(checkpoint.total_pnl),
                    "realized_pnl": str(checkpoint.realized_pnl),
                    "unrealized_pnl": str(checkpoint.unrealized_pnl),
                    "total_trades": checkpoint.total_trades,
                    "winning_trades": checkpoint.winning_trades,
                    "losing_trades": checkpoint.losing_trades,
                    "win_rate": str(checkpoint.win_rate),
                    "max_drawdown": str(checkpoint.max_drawdown),
                    "sharpe_ratio": (
                        str(checkpoint.sharpe_ratio)
                        if checkpoint.sharpe_ratio is not None
                        else None
                    ),
                    "profit_factor": (
                        str(checkpoint.profit_factor)
                        if checkpoint.profit_factor is not None
                        else None
                    ),
                    "average_win": str(checkpoint.average_win),
                    "average_loss": str(checkpoint.average_loss),
                    "created_at": checkpoint.created_at.isoformat(),
                },
            },
            status=status.HTTP_200_OK,
        )


# Execution-specific endpoints (task 14)
