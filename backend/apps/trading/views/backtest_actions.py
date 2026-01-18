"""Views for BacktestTask lifecycle operations."""

import logging
from datetime import timedelta
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTasks, Executions
from apps.trading.services.lock import TaskLockManager
from apps.trading.views._helpers import (
    TaskExecutionPagination,
    _get_execution_metrics_or_none,
    _paginate_list_by_page,
)

logger = logging.getLogger(__name__)


class BacktestTaskStartView(APIView):
    """Start a backtest task."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """Start backtest task execution."""
        try:
            task = BacktestTasks.objects.get(id=task_id, user=request.user.pk)
        except BacktestTasks.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        if task.status == TaskStatus.RUNNING:
            return Response(
                {"error": "Task is already running according to database status"},
                status=status.HTTP_409_CONFLICT,
            )

        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)

        if lock_info is not None:
            if not lock_info.is_stale:
                return Response(
                    {"error": "Task has an active lock. The task may already be running."},
                    status=status.HTTP_409_CONFLICT,
                )

            logger.warning(
                "Cleaning up stale lock for backtest task %d before starting",
                task_id,
            )
            lock_manager.release_lock(TaskType.BACKTEST, task_id)

            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.STOPPED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task.start()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)

        now = timezone.now()
        execution: Executions | None
        try:
            with transaction.atomic():
                last_num = (
                    Executions.objects.select_for_update()
                    .filter(task_type=TaskType.BACKTEST, task_id=task_id)
                    .order_by("-execution_number")
                    .values_list("execution_number", flat=True)
                    .first()
                )
                next_num = int(last_num or 0) + 1
                execution = Executions.objects.create(
                    task_type=TaskType.BACKTEST,
                    task_id=task_id,
                    execution_number=next_num,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    started_at=now,
                    logs=[
                        {
                            "timestamp": now.isoformat(),
                            "level": "INFO",
                            "message": "Execution queued",
                        }
                    ],
                )
        except IntegrityError:
            execution = task.get_latest_execution()

        from apps.trading.tasks import run_backtest_task

        cast(Any, run_backtest_task).delay(
            task.pk, execution_id=execution.pk if execution else None
        )

        return Response(
            {"message": "Backtest task started successfully", "task_id": task.pk},
            status=status.HTTP_202_ACCEPTED,
        )


class BacktestTaskStopView(APIView):
    """Stop a running backtest task."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """Stop backtest task execution."""
        try:
            task = BacktestTasks.objects.get(id=task_id, user=request.user.pk)
        except BacktestTasks.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
        has_active_lock = lock_info is not None and not lock_info.is_stale

        db_is_running = task.status == TaskStatus.RUNNING
        if not db_is_running and not has_active_lock:
            return Response({"error": "Task is not running"}, status=status.HTTP_400_BAD_REQUEST)

        if not db_is_running and has_active_lock:
            logger.warning(
                "Backtest task %d has active lock but database status is %s. Proceeding with stop.",
                task_id,
                task.status,
            )

        if has_active_lock:
            lock_manager.set_cancellation_flag(TaskType.BACKTEST, task_id)
        else:
            if lock_info:
                lock_manager.release_lock(TaskType.BACKTEST, task_id)

        task.status = TaskStatus.STOPPED
        task.save(update_fields=["status", "updated_at"])

        latest_execution = task.get_latest_execution()
        if latest_execution and latest_execution.status == TaskStatus.RUNNING:
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])
        return Response(
            {"id": task.pk, "status": TaskStatus.STOPPED, "message": "Task stop initiated"},
            status=status.HTTP_200_OK,
        )


class BacktestTaskStatusView(APIView):
    """Get current status of a backtest task."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """Get current task status and execution details."""
        try:
            task = BacktestTasks.objects.get(id=task_id, user=request.user.pk)
        except BacktestTasks.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        lock_manager = TaskLockManager()

        if task.status == TaskStatus.RUNNING and latest_execution:
            lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
            is_stale = lock_info is None or lock_info.is_stale

            execution_completed = latest_execution.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.STOPPED,
            ]

            # When a task is (re)started, there's a short window where:
            # - DB status is RUNNING (set by /start/)
            # - The new TaskExecution isn't created yet (created by Celery)
            # - The Celery lock isn't acquired yet
            # Treat that as "pending new execution" rather than "stale".
            grace_period_seconds = 30
            recently_updated = (
                task.updated_at is not None
                and timezone.now() - task.updated_at < timedelta(seconds=grace_period_seconds)
            )

            if execution_completed and is_stale and not recently_updated:
                logger.warning(
                    "Detected stale task %d (execution_status=%s, is_stale=%s), auto-completing",
                    task_id,
                    latest_execution.status,
                    is_stale,
                )

                if lock_info:
                    lock_manager.release_lock(TaskType.BACKTEST, task_id)

                task.status = latest_execution.status
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # If the API queued an execution but no worker ever started it (no lock acquired),
        # fail the execution so users see a clear error instead of missing logs.
        if (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
            started_at = latest_execution.started_at
            startup_timeout_seconds = 120
            if (
                lock_info is None
                and started_at is not None
                and (timezone.now() - started_at) > timedelta(seconds=startup_timeout_seconds)
                and int(latest_execution.progress or 0) == 0
            ):
                msg = "Execution did not start (no worker lock acquired)"
                try:
                    latest_execution.add_log("ERROR", msg)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

                latest_execution.status = TaskStatus.FAILED
                latest_execution.completed_at = timezone.now()
                latest_execution.error_message = msg
                latest_execution.save(
                    update_fields=["status", "completed_at", "error_message", "logs"]
                )

                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        if (
            task.status == TaskStatus.STOPPED
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            logger.info(
                "Task %d is stopped but execution still running, updating execution status",
                task_id,
            )

            lock_info = lock_manager.get_lock_info(TaskType.BACKTEST, task_id)
            if lock_info:
                lock_manager.release_lock(TaskType.BACKTEST, task_id)

            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])
            latest_execution.refresh_from_db()

        pending_new_execution = (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status
            in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]
        )

        if pending_new_execution:
            reported_progress = 0
        elif latest_execution:
            reported_progress = latest_execution.progress
        else:
            reported_progress = 0

        execution_data = None
        if latest_execution:
            execution_data = {
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

        response_data = {
            "task_id": task.pk,
            "task_type": "backtest",
            "status": task.status,
            "progress": reported_progress,
            "pending_new_execution": pending_new_execution,
            "started_at": (
                latest_execution.started_at.isoformat()
                if latest_execution and latest_execution.started_at
                else None
            ),
            "completed_at": (
                latest_execution.completed_at.isoformat()
                if latest_execution and latest_execution.completed_at
                else None
            ),
            "error_message": (latest_execution.error_message or None) if latest_execution else None,
            "execution": execution_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class BacktestTaskExecutionsView(APIView):
    """Get execution history for a backtest task."""

    permission_classes = [IsAuthenticated]
    pagination_class = TaskExecutionPagination

    def get(self, request: Request, task_id: int) -> Response:
        """Get execution history for backtest task."""
        try:
            task = BacktestTasks.objects.get(id=task_id, user=request.user.pk)
        except BacktestTasks.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        executions = task.get_execution_history()

        from apps.trading.serializers import TaskExecutionListSerializer

        paginator = self.pagination_class()
        paginated = paginator.paginate_queryset(executions, request)
        serializer = TaskExecutionListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class BacktestTaskExportView(APIView):
    """Export backtest results as JSON."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """Export complete backtest results."""
        try:
            task = BacktestTasks.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTasks.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {"error": "No execution found for this task"}, status=status.HTTP_404_NOT_FOUND
            )

        metrics_obj = _get_execution_metrics_or_none(latest_execution)
        if not metrics_obj:
            return Response(
                {"error": "No metrics available for export"},
                status=status.HTTP_404_NOT_FOUND,
            )
        metrics = None
        if metrics_obj:
            metrics = {
                "total_return": str(metrics_obj.total_return),
                "total_pnl": str(metrics_obj.total_pnl),
                "realized_pnl": str(getattr(metrics_obj, "realized_pnl", metrics_obj.total_pnl)),
                "unrealized_pnl": str(getattr(metrics_obj, "unrealized_pnl", "0.00")),
                "total_trades": metrics_obj.total_trades,
                "winning_trades": metrics_obj.winning_trades,
                "losing_trades": metrics_obj.losing_trades,
                "win_rate": str(metrics_obj.win_rate),
                "max_drawdown": str(metrics_obj.max_drawdown),
                "sharpe_ratio": str(metrics_obj.sharpe_ratio) if metrics_obj.sharpe_ratio else None,
                "profit_factor": (
                    str(metrics_obj.profit_factor) if metrics_obj.profit_factor else None
                ),
                "average_win": str(metrics_obj.average_win) if metrics_obj.average_win else None,
                "average_loss": str(metrics_obj.average_loss) if metrics_obj.average_loss else None,
                "trade_log": metrics_obj.trade_log or [],
                "strategy_events": metrics_obj.strategy_events or [],
            }

        strategy_type = task.config.strategy_type if task.config else None
        export_data = {
            "task": {
                "id": task.pk,
                "name": task.name,
                "description": task.description,
                "strategy_type": strategy_type,
                "instrument": task.instrument,
                "start_time": task.start_time.isoformat(),
                "end_time": task.end_time.isoformat(),
                "status": task.status,
            },
            "configuration": {
                "id": task.config.pk if task.config else None,
                "name": task.config.name if task.config else None,
                "strategy_type": strategy_type,
                "parameters": task.config.parameters if task.config else {},
            },
            "execution": {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "logs": latest_execution.logs or [],
            },
            "metrics": metrics,
            "exported_at": timezone.now().isoformat(),
        }

        return Response(export_data, status=status.HTTP_200_OK)


class BacktestTaskLogsView(APIView):
    """Get logs for a backtest task with pagination and filtering."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _collect_logs(
        executions_query: QuerySet, level: str | None
    ) -> list[dict[str, str | int | None]]:
        all_logs = []
        for execution in executions_query:
            logs = execution.logs if isinstance(execution.logs, list) else []
            for log_entry in logs:
                if level and log_entry.get("level") != level:
                    continue

                all_logs.append(
                    {
                        "timestamp": log_entry.get("timestamp"),
                        "level": log_entry.get("level"),
                        "message": log_entry.get("message"),
                        "execution_id": execution.pk,
                        "execution_number": execution.execution_number,
                    }
                )
        return all_logs

    def get(self, request: Request, task_id: int) -> Response:
        """Get task logs with pagination and filtering."""
        try:
            BacktestTasks.objects.get(id=task_id, user=request.user.pk)
        except BacktestTasks.DoesNotExist:
            return Response({"error": "Backtest task not found"}, status=status.HTTP_404_NOT_FOUND)

        execution_id = request.query_params.get("execution_id")
        level = request.query_params.get("level")

        executions_query = Executions.objects.filter(
            task_type="backtest", task_id=task_id
        ).order_by("execution_number")

        if execution_id:
            try:
                executions_query = executions_query.filter(id=int(execution_id))
            except ValueError:
                return Response(
                    {"error": "Invalid execution_id"}, status=status.HTTP_400_BAD_REQUEST
                )

        all_logs = self._collect_logs(executions_query, level)
        all_logs.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

        pagination = _paginate_list_by_page(
            request=request,
            items=all_logs,
            base_url=f"/api/trading/backtest-tasks/{task_id}/logs/",
            default_page_size=100,
            max_page_size=1000,
            extra_query={
                "execution_id": execution_id,
                "level": level,
            },
        )

        return Response(pagination, status=status.HTTP_200_OK)
