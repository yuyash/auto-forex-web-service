"""Celery tasks for live trading execution."""

from __future__ import annotations

import traceback
from logging import Logger, getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from django.utils import timezone as dj_timezone

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models import CeleryTaskStatus, TaskLog, TradingTasks

logger: Logger = getLogger(name=__name__)


@shared_task(
    bind=True,
    name="trading.tasks.run_trading_task",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_trading_task(self: Any, task_id: UUID, execution_id: int | None = None) -> None:
    """Celery task wrapper for running trading tasks.

    Args:
        task_id: UUID of the TradingTasks to execute
        execution_id: Deprecated parameter (ignored)
    """
    task = None

    try:
        # Load the task to update it
        task = TradingTasks.objects.get(pk=task_id)

        # Update task status to RUNNING and record start time
        task.status = TaskStatus.RUNNING
        task.started_at = dj_timezone.now()
        task.celery_task_id = self.request.id
        task.save(update_fields=["status", "started_at", "celery_task_id"])

        # Log task start
        TaskLog.objects.create(
            task=task,
            level=LogLevel.INFO,
            message="Trading task execution started",
        )

        # Execute the trading task
        _execute_trading(task)

        # Mark as stopped (trading tasks run until stopped)
        task.refresh_from_db()
        task.status = TaskStatus.STOPPED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at"])

        # Log task completion
        TaskLog.objects.create(
            task=task,
            level=LogLevel.INFO,
            message="Trading task stopped successfully",
        )

    except TradingTasks.DoesNotExist:
        logger.error(f"TradingTasks {task_id} not found")
        raise

    except Exception as e:
        # Capture error details and update task
        error_message = str(e)
        error_traceback = traceback.format_exc()

        logger.error(
            f"Trading task {task_id} failed: {error_message}",
            exc_info=True,
        )

        if task:
            # Update task with error information
            task.status = TaskStatus.FAILED
            task.completed_at = dj_timezone.now()
            task.error_message = error_message
            task.error_traceback = error_traceback
            task.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "error_traceback",
                ]
            )

            # Log error
            TaskLog.objects.create(
                task=task,
                level=LogLevel.ERROR,
                message=f"Trading task execution failed: {type(e).__name__}: {error_message}",
            )

        # Re-raise to trigger Celery retry
        raise


def _execute_trading(task: TradingTasks) -> None:
    """Execute a trading task.

    Args:
        task: Trading task to execute
    """
    from apps.trading.services.controller import TaskController
    from apps.trading.services.executor import TradingExecutor
    from apps.trading.services.registry import register_all_strategies, registry
    from apps.trading.services.source import LiveTickDataSource

    # Register all strategies
    register_all_strategies()

    # Create strategy instance
    strategy = registry.create(
        instrument=task.instrument,
        pip_size=task.pip_size or task.config.get_pip_size(),
        strategy_config=task.config,
        trading_mode=task.trading_mode,
    )

    # Create data source for live ticks
    channel = f"live:{task.oanda_account.account_id}:{task.instrument}"
    data_source = LiveTickDataSource(
        channel=channel,
        instrument=task.instrument,
    )

    # Create controller
    controller = TaskController(
        task_name="trading.tasks.run_trading_task",
        instance_key=str(task.pk),
    )

    # Create executor
    executor = TradingExecutor(
        task=task,
        strategy=strategy,
        data_source=data_source,
        controller=controller,
    )

    # Execute
    executor.execute()


@shared_task(bind=True, name="trading.tasks.stop_trading_task")
def stop_trading_task(self: Any, task_id: UUID, mode: str = "graceful") -> None:
    """Request stop for a running trading task.

    This handles complex cleanup operations like closing positions.

    Args:
        task_id: UUID of the trading task to stop
        mode: Stop mode ('immediate', 'graceful', 'graceful_close')
    """
    task_name = "trading.tasks.run_trading_task"
    instance_key = str(task_id)
    CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
        status=CeleryTaskStatus.Status.STOP_REQUESTED,
        status_message=f"stop_requested mode={mode}",
        last_heartbeat_at=dj_timezone.now(),
    )

    logger.info(f"Stop requested for trading task {task_id} (mode={mode})")


@shared_task(bind=True, name="trading.tasks.async_stop_trading_task")
def async_stop_trading_task(self: Any, task_id: UUID, mode: str = "graceful") -> dict[str, Any]:
    """Asynchronously stop a running trading task.

    This task handles the complete stop process for trading tasks including:
    1. Setting stop flag in CeleryTaskStatus (graceful cooperative stop)
    2. Waiting for the task to stop itself
    3. Updating the task status in the database if needed

    Note: The market publisher task (publish_oanda_ticks) is NOT stopped because
    it's a shared singleton per OANDA account that may be used by other trading tasks.
    The supervisor (ensure_tick_pubsub_running) manages the publisher lifecycle.

    Trading tasks use a graceful stop mechanism where the running task checks
    for stop requests and cleans up properly (e.g., closing positions).

    Args:
        task_id: UUID of the trading task to stop
        mode: Stop mode ('immediate', 'graceful', 'graceful_close')

    Returns:
        dict: Result containing success status and message
    """
    import time

    from celery import current_app

    logger.info(
        "Async stop trading task started",
        extra={"task_id": task_id, "mode": mode},
    )

    try:
        from apps.trading.models import TradingTasks

        # Get the task
        try:
            task = TradingTasks.objects.get(pk=task_id)
        except TradingTasks.DoesNotExist:
            error_msg = f"Trading task {task_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Check if task is in a stoppable state
        if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            error_msg = f"Task {task_id} is not in a stoppable state (status: {task.status})"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # Set stop flag for the trading task (graceful cooperative stop)
        task_name = "trading.tasks.run_trading_task"
        instance_key = str(task_id)
        CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
            status=CeleryTaskStatus.Status.STOP_REQUESTED,
            status_message=f"stop_requested mode={mode}",
            last_heartbeat_at=dj_timezone.now(),
        )

        logger.info(
            "Stop flag set for trading task",
            extra={"task_id": task_id, "mode": mode},
        )

        # Note: We do NOT stop the market publisher (publish_oanda_ticks) because:
        # 1. It's a shared singleton per OANDA account
        # 2. Other trading tasks may be using the same account
        # 3. The supervisor manages its lifecycle

        # Wait for the trading task to stop itself (with timeout)
        max_wait_seconds = 30
        check_interval = 1
        elapsed = 0

        while elapsed < max_wait_seconds:
            time.sleep(check_interval)
            elapsed += check_interval

            task.refresh_from_db()
            if task.status == TaskStatus.STOPPED:
                logger.info(
                    "Trading task stopped gracefully",
                    extra={"task_id": task_id, "elapsed_seconds": elapsed},
                )
                return {
                    "success": True,
                    "message": f"Trading task {task_id} stopped gracefully",
                    "task_id": task_id,
                    "elapsed_seconds": elapsed,
                }

        # If task didn't stop within timeout, force status update
        logger.warning(
            "Trading task did not stop within timeout, forcing status update",
            extra={"task_id": task_id, "timeout_seconds": max_wait_seconds},
        )

        # Revoke the Celery task as last resort
        if task.celery_task_id:
            try:
                current_app.control.revoke(task.celery_task_id, terminate=True)
                logger.info(
                    "Celery task revoked after timeout",
                    extra={"task_id": task_id, "celery_task_id": task.celery_task_id},
                )
            except Exception as e:
                logger.warning(
                    f"Failed to revoke Celery task: {str(e)}",
                    extra={"task_id": task_id, "celery_task_id": task.celery_task_id},
                    exc_info=True,
                )

        task.status = TaskStatus.STOPPED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])

        TaskLog.objects.create(
            task=task,
            level=LogLevel.WARNING,
            message=f"Trading task stopped after timeout ({max_wait_seconds}s)",
        )

        return {
            "success": True,
            "message": f"Trading task {task_id} stopped (forced after timeout)",
            "task_id": task_id,
            "forced": True,
        }

    except Exception as e:
        error_msg = f"Unexpected error stopping trading task {task_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}


@shared_task(bind=True, name="trading.tasks.async_stop_backtest_task")
def async_stop_backtest_task(self: Any, task_id: UUID) -> dict[str, Any]:
    """Asynchronously stop a running backtest task.

    This task handles the complete stop process for backtest tasks including:
    1. Stopping the market publisher task (publish_ticks_for_backtest)
    2. Revoking the Celery task (immediate termination)
    3. Updating the task status in the database
    4. Recording completion timestamp

    Args:
        task_id: UUID of the backtest task to stop

    Returns:
        dict: Result containing success status and message
    """
    from celery import current_app

    logger.info(
        "Async stop backtest task started",
        extra={"task_id": task_id},
    )

    try:
        from apps.trading.models import BacktestTasks

        # Get the task
        try:
            task = BacktestTasks.objects.get(pk=task_id)
        except BacktestTasks.DoesNotExist:
            error_msg = f"Backtest task {task_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Check if task is in a stoppable state
        if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            error_msg = f"Task {task_id} is not in a stoppable state (status: {task.status})"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # Step 1: Stop the market publisher task for backtest
        # The publisher uses request_id as instance_key
        # We need to find the request_id associated with this backtest
        publisher_task_name = "market.tasks.publish_ticks_for_backtest"

        # Try to find and stop any publisher tasks for this backtest
        # The request_id pattern is typically based on the backtest task
        from apps.market.models import CeleryTaskStatus as MarketCeleryTaskStatus

        # Find all running publisher tasks and stop those related to this backtest
        # The instance_key for backtest publisher is the request_id
        publisher_tasks = MarketCeleryTaskStatus.objects.filter(
            task_name=publisher_task_name,
            status=MarketCeleryTaskStatus.Status.RUNNING,
        )

        stopped_publishers = 0
        for pub_task in publisher_tasks:
            # Stop the publisher task
            MarketCeleryTaskStatus.objects.filter(
                task_name=publisher_task_name,
                instance_key=pub_task.instance_key,
            ).update(
                status=MarketCeleryTaskStatus.Status.STOP_REQUESTED,
                status_message=f"stop_requested by backtest task {task_id}",
                last_heartbeat_at=dj_timezone.now(),
            )

            # Also revoke the Celery task if we have the ID
            if pub_task.celery_task_id:
                try:
                    current_app.control.revoke(pub_task.celery_task_id, terminate=True)
                    logger.info(
                        "Market publisher Celery task revoked",
                        extra={
                            "backtest_task_id": task_id,
                            "publisher_celery_task_id": pub_task.celery_task_id,
                            "request_id": pub_task.instance_key,
                        },
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to revoke publisher Celery task: {str(e)}",
                        extra={
                            "backtest_task_id": task_id,
                            "publisher_celery_task_id": pub_task.celery_task_id,
                        },
                        exc_info=True,
                    )

            stopped_publishers += 1

        if stopped_publishers > 0:
            logger.info(
                "Stop flag set for market publisher(s)",
                extra={"backtest_task_id": task_id, "count": stopped_publishers},
            )
        else:
            logger.info(
                "No active market publisher tasks found for backtest",
                extra={"backtest_task_id": task_id},
            )

        # Step 2: Revoke the backtest Celery task if it exists (this may take time)
        if task.celery_task_id:
            try:
                current_app.control.revoke(task.celery_task_id, terminate=True)
                logger.info(
                    "Backtest Celery task revoked",
                    extra={"task_id": task_id, "celery_task_id": task.celery_task_id},
                )
            except Exception as e:
                logger.warning(
                    f"Failed to revoke backtest Celery task: {str(e)}",
                    extra={"task_id": task_id, "celery_task_id": task.celery_task_id},
                    exc_info=True,
                )
                # Continue with status update even if revoke fails

        # Step 3: Update task status
        task.status = TaskStatus.STOPPED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])

        # Log task stop
        TaskLog.objects.create(
            task=task,
            level=LogLevel.INFO,
            message="Backtest task stopped via async stop request",
        )

        logger.info(
            "Backtest task stopped successfully",
            extra={"task_id": task_id, "publishers_stopped": stopped_publishers},
        )

        return {
            "success": True,
            "message": f"Backtest task {task_id} stopped successfully",
            "task_id": task_id,
            "publishers_stopped": stopped_publishers,
        }

    except Exception as e:
        error_msg = f"Unexpected error stopping backtest task {task_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}


def async_stop_task(self: Any, task_id: UUID, task_type: str) -> dict[str, Any]:
    """Asynchronously stop a running task (backtest or trading).

    This task handles the complete stop process including:
    1. Revoking the Celery task
    2. Updating the task status in the database
    3. Recording completion timestamp

    Args:
        task_id: UUID of the task to stop
        task_type: Type of task ('backtest' or 'trading')

    Returns:
        dict: Result containing success status and message
    """
    from celery import current_app

    logger.info(
        "Async stop task started",
        extra={"task_id": task_id, "task_type": task_type},
    )

    try:
        # Import models based on task type
        if task_type == "backtest":
            from apps.trading.models import BacktestTasks as TaskModel
        elif task_type == "trading":
            from apps.trading.models import TradingTasks as TaskModel
        else:
            error_msg = f"Invalid task type: {task_type}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Get the task
        try:
            task = TaskModel.objects.get(pk=task_id)
        except TaskModel.DoesNotExist:
            error_msg = f"Task {task_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # Check if task is in a stoppable state
        if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            error_msg = f"Task {task_id} is not in a stoppable state (status: {task.status})"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # Revoke the Celery task if it exists
        if task.celery_task_id:
            try:
                current_app.control.revoke(task.celery_task_id, terminate=True)
                logger.info(
                    "Celery task revoked",
                    extra={"task_id": task_id, "celery_task_id": task.celery_task_id},
                )
            except Exception as e:
                logger.warning(
                    f"Failed to revoke Celery task: {str(e)}",
                    extra={"task_id": task_id, "celery_task_id": task.celery_task_id},
                    exc_info=True,
                )
                # Continue with status update even if revoke fails

        # Update task status
        task.status = TaskStatus.STOPPED
        task.completed_at = dj_timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])

        # Log task stop
        TaskLog.objects.create(
            task=task,
            level=LogLevel.INFO,
            message="Task stopped via async stop request",
        )

        logger.info(
            "Task stopped successfully",
            extra={"task_id": task_id, "task_type": task_type},
        )

        return {
            "success": True,
            "message": f"Task {task_id} stopped successfully",
            "task_id": task_id,
            "task_type": task_type,
        }

    except Exception as e:
        error_msg = f"Unexpected error stopping task {task_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}
