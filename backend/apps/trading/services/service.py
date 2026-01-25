"""Task service layer for managing task lifecycle and execution.

This module provides the service layer for task management, including:
- Task creation and submission to Celery
- Task cancellation, restart, and resume operations
- Task status retrieval and synchronization
- Task logs and metrics retrieval with filtering and pagination
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from logging import Logger
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from apps.trading.enums import LogLevel, TaskStatus, TaskType
    from apps.trading.models import BacktestTasks, TaskLog, TaskMetric, TradingTasks

# Configure structured logging
logger: Logger = logging.getLogger(name=__name__)


class TaskService(ABC):
    """Abstract base class for task service operations.

    Defines the interface for task lifecycle management, including:
    - Task creation and submission
    - Task cancellation, restart, and resume
    - Task status retrieval
    - Task logs and metrics retrieval
    """

    @abstractmethod
    def create_task(
        self,
        *,
        task_type: TaskType,
        user_id: int,
        name: str,
        config_id: int,
        **kwargs: dict,
    ) -> BacktestTasks | TradingTasks:
        """Create a new task with initial configuration.

        Args:
            task_type: Type of task (BACKTEST or TRADING)
            user_id: ID of the user creating the task
            name: Human-readable name for the task
            config_id: ID of the strategy configuration to use
            **kwargs: Additional task-specific parameters

        Returns:
            BacktestTasks | TradingTasks: The created task instance

        Raises:
            ValueError: If task configuration is invalid
        """
        ...

    @abstractmethod
    def submit_task(
        self,
        task: BacktestTasks | TradingTasks,
    ) -> BacktestTasks | TradingTasks:
        """Submit a task to Celery for execution.

        Creates a Celery task and updates the Task model with the Celery task ID.
        Updates task status to RUNNING and records started_at timestamp.

        Args:
            task: Task instance to submit

        Returns:
            BacktestTasks | TradingTasks: The updated task instance

        Raises:
            ValueError: If task is not in PENDING status
            RuntimeError: If Celery submission fails
        """
        ...

    @abstractmethod
    def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a running task.

        Revokes the Celery task and updates the Task status to STOPPED.
        Records completed_at timestamp.

        Args:
            task_id: UUID of the task to cancel

        Returns:
            bool: True if task was successfully cancelled, False otherwise

        Raises:
            ValueError: If task does not exist
        """
        ...

    @abstractmethod
    def restart_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks:
        """Restart a task from the beginning, clearing all execution data.

        Clears all previous execution data (celery_task_id, started_at, completed_at,
        error_message, error_traceback, result_data) and resets status to PENDING.
        Increments retry_count.

        Args:
            task_id: UUID of the task to restart

        Returns:
            BacktestTasks | TradingTasks: The restarted task instance

        Raises:
            ValueError: If task cannot be restarted (e.g., currently running)
            ValueError: If retry_count exceeds max_retries
        """
        ...

    @abstractmethod
    def resume_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks:
        """Resume a cancelled task, preserving execution context.

        Preserves existing execution data (started_at, logs, metrics) but clears
        celery_task_id and completed_at. Resets status to PENDING.

        Args:
            task_id: UUID of the task to resume

        Returns:
            BacktestTasks | TradingTasks: The resumed task instance

        Raises:
            ValueError: If task cannot be resumed (e.g., not cancelled)
        """
        ...

    @abstractmethod
    def get_task_status(self, task_id: UUID) -> TaskStatus:
        """Get current task status.

        Retrieves the current status of a task, optionally synchronizing
        with Celery task state.

        Args:
            task_id: UUID of the task

        Returns:
            TaskStatus: Current task status

        Raises:
            ValueError: If task does not exist
        """
        ...

    @abstractmethod
    def get_task_logs(
        self,
        task_id: UUID,
        *,
        level: LogLevel | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskLog]:
        """Retrieve task execution logs with filtering and pagination.

        Args:
            task_id: UUID of the task
            level: Optional log level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            limit: Maximum number of logs to return (default: 100)
            offset: Number of logs to skip for pagination (default: 0)

        Returns:
            list[TaskLog]: List of task log entries

        Raises:
            ValueError: If task does not exist
        """
        ...

    @abstractmethod
    def get_task_metrics(
        self,
        task_id: UUID,
        *,
        metric_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[TaskMetric]:
        """Retrieve task execution metrics with filtering.

        Args:
            task_id: UUID of the task
            metric_name: Optional metric name filter
            start_time: Optional start time for time range filter
            end_time: Optional end time for time range filter

        Returns:
            list[TaskMetric]: List of task metric entries

        Raises:
            ValueError: If task does not exist
        """
        ...


class TaskServiceProtocol(Protocol):
    """Protocol for task service implementations.

    This protocol defines the expected interface for task service implementations,
    allowing for type checking and dependency injection.
    """

    def create_task(
        self,
        *,
        task_type: TaskType,
        user_id: int,
        name: str,
        config_id: int,
        **kwargs: dict,
    ) -> BacktestTasks | TradingTasks: ...

    def submit_task(
        self,
        task: BacktestTasks | TradingTasks,
    ) -> BacktestTasks | TradingTasks: ...

    def cancel_task(self, task_id: UUID) -> bool: ...

    def restart_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks: ...

    def resume_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks: ...

    def get_task_status(self, task_id: UUID) -> TaskStatus: ...

    def get_task_logs(
        self,
        task_id: UUID,
        *,
        level: LogLevel | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskLog]: ...

    def get_task_metrics(
        self,
        task_id: UUID,
        *,
        metric_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[TaskMetric]: ...


class TaskServiceImpl(TaskService):
    """Implementation of TaskService for managing task lifecycle.

    This service provides concrete implementations for:
    - Task creation with validation
    - Task submission to Celery
    - Task cancellation, restart, and resume operations
    - Task status retrieval and synchronization
    - Task logs and metrics retrieval with filtering
    """

    def create_task(
        self,
        *,
        task_type: TaskType,
        user_id: int,
        name: str,
        config_id: int,
        **kwargs: dict,
    ) -> BacktestTasks | TradingTasks:
        """Create a new task with initial configuration.

        Args:
            task_type: Type of task (BACKTEST or TRADING)
            user_id: ID of the user creating the task
            name: Human-readable name for the task
            config_id: ID of the strategy configuration to use
            **kwargs: Additional task-specific parameters

        Returns:
            BacktestTasks | TradingTasks: The created task instance

        Raises:
            ValueError: If task configuration is invalid
        """
        from apps.accounts.models import User
        from apps.trading.enums import TaskType as TaskTypeEnum
        from apps.trading.models import BacktestTasks, StrategyConfigurations, TradingTasks

        logger.info(
            "Creating task",
            extra={
                "task_type": task_type,
                "user_id": user_id,
                "task_name": name,
                "config_id": config_id,
            },
        )

        try:
            # Get user and config
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist as e:
                logger.error(
                    "User not found",
                    extra={"user_id": user_id},
                    exc_info=True,
                )
                raise ValueError(f"User with id {user_id} does not exist") from e

            try:
                config = StrategyConfigurations.objects.get(id=config_id)
            except StrategyConfigurations.DoesNotExist as e:
                logger.error(
                    "Strategy configuration not found",
                    extra={"config_id": config_id},
                    exc_info=True,
                )
                raise ValueError(
                    f"Strategy configuration with id {config_id} does not exist"
                ) from e

            # Create task based on type
            if task_type == TaskTypeEnum.BACKTEST:
                # Extract backtest-specific parameters
                start_time = kwargs.get("start_time")
                end_time = kwargs.get("end_time")
                if not start_time or not end_time:
                    logger.error(
                        "Missing required backtest parameters",
                        extra={"start_time": start_time, "end_time": end_time},
                    )
                    raise ValueError("start_time and end_time are required for backtest tasks")

                task = BacktestTasks.objects.create(
                    user=user,
                    config=config,
                    name=name,
                    description=kwargs.get("description", ""),
                    data_source=kwargs.get("data_source", "postgresql"),
                    start_time=start_time,
                    end_time=end_time,
                    initial_balance=kwargs.get("initial_balance", 10000),
                    commission_per_trade=kwargs.get("commission_per_trade", 0),
                    instrument=kwargs.get("instrument", "USD_JPY"),
                    _pip_size=kwargs.get("pip_size", 0.01),
                    trading_mode=kwargs.get("trading_mode", "netting"),
                )
            elif task_type == TaskTypeEnum.TRADING:
                # Extract trading-specific parameters
                oanda_account_id = kwargs.get("oanda_account_id")
                if not oanda_account_id:
                    logger.error("Missing required trading parameter: oanda_account_id")
                    raise ValueError("oanda_account_id is required for trading tasks")

                from apps.market.models import OandaAccounts

                try:
                    oanda_account = OandaAccounts.objects.get(id=oanda_account_id)
                except OandaAccounts.DoesNotExist as e:
                    logger.error(
                        "OANDA account not found",
                        extra={"oanda_account_id": oanda_account_id},
                        exc_info=True,
                    )
                    raise ValueError(
                        f"OANDA account with id {oanda_account_id} does not exist"
                    ) from e

                task = TradingTasks.objects.create(
                    user=user,
                    config=config,
                    oanda_account=oanda_account,
                    name=name,
                    description=kwargs.get("description", ""),
                    sell_on_stop=kwargs.get("sell_on_stop", False),
                    instrument=kwargs.get("instrument", "USD_JPY"),
                    _pip_size=kwargs.get("pip_size", 0.01),
                    trading_mode=kwargs.get("trading_mode", "netting"),
                )
            else:
                logger.error("Unknown task type", extra={"task_type": task_type})
                raise ValueError(f"Unknown task type: {task_type}")

            logger.info(
                "Task created successfully",
                extra={"task_id": task.pk, "task_type": task_type},
            )
            return task

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error creating task",
                extra={
                    "task_type": task_type,
                    "user_id": user_id,
                    "config_id": config_id,
                },
                exc_info=True,
            )
            raise ValueError(f"Failed to create task: {str(e)}") from e

    def submit_task(
        self,
        task: BacktestTasks | TradingTasks,
    ) -> BacktestTasks | TradingTasks:
        """Submit a task to Celery for execution.

        Creates a Celery task and updates the Task model with the Celery task ID.
        Updates task status to RUNNING and records started_at timestamp.

        Args:
            task: Task instance to submit

        Returns:
            BacktestTasks | TradingTasks: The updated task instance

        Raises:
            ValueError: If task is not in PENDING status
            RuntimeError: If Celery submission fails
        """
        from uuid import uuid4

        from django.utils import timezone

        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks
        from apps.trading.tasks import run_backtest_task, run_trading_task

        logger.info(
            "Submitting task",
            extra={"task_id": task.pk, "task_status": task.status},
        )

        try:
            # Validate task status
            if task.status != TaskStatus.CREATED:
                logger.warning(
                    "Task not in PENDING status",
                    extra={"task_id": task.pk, "current_status": task.status},
                )
                raise ValueError(
                    f"Task must be in PENDING status to submit (current status: {task.status})"
                )

            # Validate task configuration
            is_valid, error_message = task.validate_configuration()
            if not is_valid:
                logger.error(
                    "Task configuration validation failed",
                    extra={"task_id": task.pk, "error": error_message},
                )
                raise ValueError(f"Task configuration is invalid: {error_message}")

            # Determine which Celery task to call based on task type
            if isinstance(task, BacktestTasks):
                celery_task = run_backtest_task
            else:
                celery_task = run_trading_task

            # Generate a unique Celery task ID
            celery_task_id = str(uuid4())

            try:
                # Submit to Celery
                result = celery_task.apply_async(
                    args=[task.pk],
                    task_id=celery_task_id,
                )

                # Update task with Celery task ID and status
                task.celery_task_id = result.id
                task.status = TaskStatus.RUNNING
                task.started_at = timezone.now()
                task.save(update_fields=["celery_task_id", "status", "started_at", "updated_at"])

                logger.info(
                    "Task submitted successfully",
                    extra={
                        "task_id": task.pk,
                        "celery_task_id": result.id,
                    },
                )

                return task

            except Exception as e:
                logger.error(
                    "Celery submission failed",
                    extra={"task_id": task.pk, "celery_task_id": celery_task_id},
                    exc_info=True,
                )
                raise RuntimeError(f"Failed to submit task to Celery: {str(e)}") from e

        except (ValueError, RuntimeError):
            # Re-raise expected exceptions as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error submitting task",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            raise RuntimeError(f"Unexpected error during task submission: {str(e)}") from e

    def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a running task.

        Revokes the Celery task and updates the Task status to STOPPED.
        Records completed_at timestamp.

        Args:
            task_id: UUID of the task to cancel

        Returns:
            bool: True if task was successfully cancelled, False otherwise

        Raises:
            ValueError: If task does not exist
        """
        from apps.trading.models import BacktestTasks, TradingTasks

        logger.info("Cancelling task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Use the task's cancel method
            success = task.cancel()

            if success:
                logger.info(
                    "Task cancelled successfully",
                    extra={"task_id": str(task_id)},
                )
            else:
                logger.warning(
                    "Task cancellation failed",
                    extra={"task_id": str(task_id), "task_status": task.status},
                )

            return success

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error cancelling task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to cancel task: {str(e)}") from e

    def restart_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks:
        """Restart a task from the beginning, clearing all execution data.

        Clears all previous execution data (celery_task_id, started_at, completed_at,
        error_message, error_traceback, result_data) and resets status to PENDING.
        Increments retry_count.

        Args:
            task_id: UUID of the task to restart

        Returns:
            BacktestTasks | TradingTasks: The restarted task instance

        Raises:
            ValueError: If task cannot be restarted (e.g., currently running)
            ValueError: If retry_count exceeds max_retries
        """
        from apps.trading.models import BacktestTasks, TradingTasks

        logger.info("Restarting task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Check retry count limit
            if task.retry_count >= task.max_retries:
                logger.warning(
                    "Task retry limit exceeded",
                    extra={
                        "task_id": str(task_id),
                        "retry_count": task.retry_count,
                        "max_retries": task.max_retries,
                    },
                )
                raise ValueError(
                    f"Task has reached maximum retry limit "
                    f"(retry_count={task.retry_count}, max_retries={task.max_retries})"
                )

            # Use the task's restart method
            success = task.restart()
            if not success:
                logger.warning(
                    "Task restart failed",
                    extra={"task_id": str(task_id), "task_status": task.status},
                )
                raise ValueError("Task cannot be restarted in its current state")

            logger.info(
                "Task restarted, resubmitting",
                extra={"task_id": str(task_id), "retry_count": task.retry_count},
            )

            # Resubmit the task
            return self.submit_task(task)

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error restarting task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to restart task: {str(e)}") from e

    def resume_task(
        self,
        task_id: UUID,
    ) -> BacktestTasks | TradingTasks:
        """Resume a cancelled task, preserving execution context.

        Preserves existing execution data (started_at, logs, metrics) but clears
        celery_task_id and completed_at. Resets status to PENDING.

        Args:
            task_id: UUID of the task to resume

        Returns:
            BacktestTasks | TradingTasks: The resumed task instance

        Raises:
            ValueError: If task cannot be resumed (e.g., not cancelled)
        """
        from apps.trading.models import BacktestTasks, TradingTasks

        logger.info("Resuming task", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Use the task's resume method
            success = task.resume()
            if not success:
                logger.warning(
                    "Task resume failed",
                    extra={"task_id": str(task_id), "task_status": task.status},
                )
                raise ValueError("Task cannot be resumed in its current state")

            logger.info(
                "Task resumed, resubmitting",
                extra={"task_id": str(task_id)},
            )

            # Resubmit the task
            return self.submit_task(task)

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error resuming task",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to resume task: {str(e)}") from e

    def get_task_status(self, task_id: UUID) -> TaskStatus:
        """Get current task status.

        Retrieves the current status of a task, optionally synchronizing
        with Celery task state.

        Args:
            task_id: UUID of the task

        Returns:
            TaskStatus: Current task status

        Raises:
            ValueError: If task does not exist
        """
        from apps.trading.models import BacktestTasks, TradingTasks

        logger.debug("Getting task status", extra={"task_id": str(task_id)})

        try:
            # Try to find the task in either BacktestTasks or TradingTasks
            task = None
            try:
                task = BacktestTasks.objects.get(pk=task_id)
            except BacktestTasks.DoesNotExist:
                try:
                    task = TradingTasks.objects.get(pk=task_id)
                except TradingTasks.DoesNotExist as e:
                    logger.error(
                        "Task not found",
                        extra={"task_id": str(task_id)},
                    )
                    raise ValueError(f"Task with id {task_id} does not exist") from e

            # Synchronize with Celery state if celery_task_id is set
            if task.celery_task_id:
                try:
                    task.update_from_celery_state()
                except Exception:
                    logger.warning(
                        "Failed to synchronize with Celery state",
                        extra={"task_id": str(task_id), "celery_task_id": task.celery_task_id},
                        exc_info=True,
                    )
                    # Continue with current status if sync fails

            return task.status

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error getting task status",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to get task status: {str(e)}") from e

    def get_task_logs(
        self,
        task_id: UUID,
        *,
        level: LogLevel | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskLog]:
        """Retrieve task execution logs with filtering and pagination.

        Args:
            task_id: UUID of the task
            level: Optional log level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            limit: Maximum number of logs to return (default: 100)
            offset: Number of logs to skip for pagination (default: 0)

        Returns:
            list[TaskLog]: List of task log entries

        Raises:
            ValueError: If task does not exist
        """
        from apps.trading.models import BacktestTasks, TaskLog, TradingTasks

        logger.debug(
            "Getting task logs",
            extra={
                "task_id": str(task_id),
                "level": level,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            # Verify task exists
            task_exists = (
                BacktestTasks.objects.filter(pk=task_id).exists()
                or TradingTasks.objects.filter(pk=task_id).exists()
            )
            if not task_exists:
                logger.error(
                    "Task not found",
                    extra={"task_id": str(task_id)},
                )
                raise ValueError(f"Task with id {task_id} does not exist")

            # Build query
            queryset = TaskLog.objects.filter(task_id=task_id)

            # Apply level filter if provided
            if level is not None:
                queryset = queryset.filter(level=level)

            # Apply pagination
            queryset = queryset.order_by("timestamp")[offset : offset + limit]

            logs = list(queryset)

            logger.debug(
                "Retrieved task logs",
                extra={"task_id": str(task_id), "log_count": len(logs)},
            )

            return logs

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error getting task logs",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to get task logs: {str(e)}") from e

    def get_task_metrics(
        self,
        task_id: UUID,
        *,
        metric_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[TaskMetric]:
        """Retrieve task execution metrics with filtering.

        Args:
            task_id: UUID of the task
            metric_name: Optional metric name filter
            start_time: Optional start time for time range filter
            end_time: Optional end time for time range filter

        Returns:
            list[TaskMetric]: List of task metric entries

        Raises:
            ValueError: If task does not exist
        """
        from apps.trading.models import BacktestTasks, TaskMetric, TradingTasks

        logger.debug(
            "Getting task metrics",
            extra={
                "task_id": str(task_id),
                "metric_name": metric_name,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

        try:
            # Verify task exists
            task_exists = (
                BacktestTasks.objects.filter(pk=task_id).exists()
                or TradingTasks.objects.filter(pk=task_id).exists()
            )
            if not task_exists:
                logger.error(
                    "Task not found",
                    extra={"task_id": str(task_id)},
                )
                raise ValueError(f"Task with id {task_id} does not exist")

            # Build query
            queryset = TaskMetric.objects.filter(task_id=task_id)

            # Apply metric name filter if provided
            if metric_name is not None:
                queryset = queryset.filter(metric_name=metric_name)

            # Apply time range filters if provided
            if start_time is not None:
                queryset = queryset.filter(timestamp__gte=start_time)
            if end_time is not None:
                queryset = queryset.filter(timestamp__lte=end_time)

            # Order by timestamp
            queryset = queryset.order_by("timestamp")

            metrics = list(queryset)

            logger.debug(
                "Retrieved task metrics",
                extra={"task_id": str(task_id), "metric_count": len(metrics)},
            )

            return metrics

        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error getting task metrics",
                extra={"task_id": str(task_id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to get task metrics: {str(e)}") from e
