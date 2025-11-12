"""
Event logging utilities for the trading system.

This module provides a base EventLogger class and specialized loggers
for different event categories (trading, system, security, admin).

Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 25.1, 25.2, 25.3, 25.4, 25.5,
              26.1, 26.2, 26.3, 26.4, 26.5
"""

# pylint: disable=too-many-lines

from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model

from accounts.models import OandaAccount
from trading.event_models import Event

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as UserType
else:
    UserType = None

User = get_user_model()


class EventLogger:
    """
    Base event logger for creating Event records.

    This class provides a unified interface for logging events across
    all categories (trading, system, security, admin) with support for
    all severity levels.

    Requirements: 24.5, 25.5, 26.5
    """

    def log_event(  # pylint: disable=too-many-positional-arguments
        self,
        category: str,
        event_type: str,
        description: str,
        *,
        severity: str = "info",
        user: "UserType | None" = None,
        account: OandaAccount | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Event:
        """
        Log an event to the database.

        Args:
            category: Event category (trading, system, security, admin)
            event_type: Specific event type
            description: Human-readable event description
            severity: Event severity (debug, info, warning, error, critical)
            user: User associated with the event
            account: OANDA account associated with the event
            ip_address: IP address associated with the event
            user_agent: User agent string
            details: Additional event details as dictionary

        Returns:
            Created Event instance

        Requirements: 24.5, 25.5, 26.5
        """
        # Convert user to the correct type for Event model
        event_user = User.objects.get(pk=user.pk) if user else None
        return Event.objects.create(
            category=category,
            event_type=event_type,
            description=description,
            severity=severity,
            user=event_user,
            account=account,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )


class TradingEventLogger(EventLogger):
    """
    Specialized logger for trading events.

    Handles logging of order submissions, position changes, strategy actions,
    and P&L events.

    Requirements: 24.1, 24.2, 24.3, 24.4
    """

    def log_order_submitted(  # pylint: disable=too-many-positional-arguments
        self,
        user: "UserType",
        account: OandaAccount,
        instrument: str,
        order_type: str,
        direction: str,
        units: int,
        price: float | None = None,
        order_id: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log an order submission event.

        Requirements: 24.1
        """
        details = {
            "instrument": instrument,
            "order_type": order_type,
            "direction": direction,
            "units": units,
            "price": price,
            "order_id": order_id,
            **kwargs,
        }
        desc = f"Order submitted: {direction} {units} units of {instrument}"
        return self.log_event(
            category="trading",
            event_type="order_submitted",
            description=desc,
            severity="info",
            user=user,
            account=account,
            details=details,
        )

    def log_order_filled(  # pylint: disable=too-many-positional-arguments
        self,
        user: "UserType",
        account: OandaAccount,
        order_id: str,
        instrument: str,
        fill_price: float,
        units: int,
        **kwargs: Any,
    ) -> Event:
        """
        Log an order fill event.

        Requirements: 24.1
        """
        details = {
            "order_id": order_id,
            "instrument": instrument,
            "fill_price": fill_price,
            "units": units,
            **kwargs,
        }
        return self.log_event(
            category="trading",
            event_type="order_filled",
            description=f"Order {order_id} filled at {fill_price}",
            severity="info",
            user=user,
            account=account,
            details=details,
        )

    def log_order_cancelled(
        self,
        user: "UserType",
        account: OandaAccount,
        order_id: str,
        reason: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log an order cancellation event.

        Requirements: 24.1
        """
        details = {
            "order_id": order_id,
            "reason": reason,
            **kwargs,
        }
        desc = f"Order {order_id} cancelled"
        if reason:
            desc += f": {reason}"
        return self.log_event(
            category="trading",
            event_type="order_cancelled",
            description=desc,
            severity="info",
            user=user,
            account=account,
            details=details,
        )

    def log_order_failed(
        self,
        user: "UserType",
        account: OandaAccount,
        instrument: str,
        error_message: str,
        **kwargs: Any,
    ) -> Event:
        """
        Log an order failure event.

        Requirements: 24.1
        """
        details = {
            "instrument": instrument,
            "error_message": error_message,
            **kwargs,
        }
        return self.log_event(
            category="trading",
            event_type="order_failed",
            description=f"Order failed for {instrument}: {error_message}",
            severity="error",
            user=user,
            account=account,
            details=details,
        )

    def log_position_opened(  # pylint: disable=too-many-positional-arguments
        self,
        user: "UserType",
        account: OandaAccount,
        position_id: str,
        instrument: str,
        direction: str,
        units: int,
        entry_price: float,
        **kwargs: Any,
    ) -> Event:
        """
        Log a position opening event.

        Requirements: 24.2
        """
        details = {
            "position_id": position_id,
            "instrument": instrument,
            "direction": direction,
            "units": units,
            "entry_price": entry_price,
            **kwargs,
        }
        desc = f"Position opened: {direction} {units} units of " f"{instrument} at {entry_price}"
        return self.log_event(
            category="trading",
            event_type="position_opened",
            description=desc,
            severity="info",
            user=user,
            account=account,
            details=details,
        )

    def log_position_closed(  # pylint: disable=too-many-positional-arguments
        self,
        user: "UserType",
        account: OandaAccount,
        position_id: str,
        instrument: str,
        exit_price: float,
        realized_pnl: float,
        **kwargs: Any,
    ) -> Event:
        """
        Log a position closing event.

        Requirements: 24.2
        """
        details = {
            "position_id": position_id,
            "instrument": instrument,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
            **kwargs,
        }
        severity = "info" if realized_pnl >= 0 else "warning"
        desc = f"Position {position_id} closed at {exit_price}, " f"P&L: {realized_pnl:.2f}"
        return self.log_event(
            category="trading",
            event_type="position_closed",
            description=desc,
            severity=severity,
            user=user,
            account=account,
            details=details,
        )

    def log_strategy_started(
        self,
        user: "UserType",
        account: OandaAccount,
        strategy_name: str,
        strategy_config: dict[str, Any],
        **kwargs: Any,
    ) -> Event:
        """
        Log a strategy start event.

        Requirements: 24.3
        """
        details = {
            "strategy_name": strategy_name,
            "strategy_config": strategy_config,
            **kwargs,
        }
        return self.log_event(
            category="trading",
            event_type="strategy_started",
            description=f"Strategy '{strategy_name}' started",
            severity="info",
            user=user,
            account=account,
            details=details,
        )

    def log_strategy_stopped(
        self,
        user: "UserType",
        account: OandaAccount,
        strategy_name: str,
        reason: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a strategy stop event.

        Requirements: 24.3
        """
        details = {
            "strategy_name": strategy_name,
            "reason": reason,
            **kwargs,
        }
        desc = f"Strategy '{strategy_name}' stopped"
        if reason:
            desc += f": {reason}"
        return self.log_event(
            category="trading",
            event_type="strategy_stopped",
            description=desc,
            severity="info",
            user=user,
            account=account,
            details=details,
        )

    def log_take_profit_triggered(  # pylint: disable=too-many-positional-arguments
        self,
        user: "UserType",
        account: OandaAccount,
        position_id: str,
        instrument: str,
        trigger_price: float,
        profit: float,
        **kwargs: Any,
    ) -> Event:
        """
        Log a take-profit trigger event.

        Requirements: 24.4
        """
        details = {
            "position_id": position_id,
            "instrument": instrument,
            "trigger_price": trigger_price,
            "profit": profit,
            **kwargs,
        }
        desc = (
            f"Take-profit triggered for {position_id} at {trigger_price}, " f"profit: {profit:.2f}"
        )
        return self.log_event(
            category="trading",
            event_type="take_profit_triggered",
            description=desc,
            severity="info",
            user=user,
            account=account,
            details=details,
        )

    def log_stop_loss_triggered(  # pylint: disable=too-many-positional-arguments
        self,
        user: "UserType",
        account: OandaAccount,
        position_id: str,
        instrument: str,
        trigger_price: float,
        loss: float,
        **kwargs: Any,
    ) -> Event:
        """
        Log a stop-loss trigger event.

        Requirements: 24.4
        """
        details = {
            "position_id": position_id,
            "instrument": instrument,
            "trigger_price": trigger_price,
            "loss": loss,
            **kwargs,
        }
        desc = f"Stop-loss triggered for {position_id} at {trigger_price}, " f"loss: {loss:.2f}"
        return self.log_event(
            category="trading",
            event_type="stop_loss_triggered",
            description=desc,
            severity="warning",
            user=user,
            account=account,
            details=details,
        )


class SystemEventLogger(EventLogger):
    """
    Specialized logger for system events.

    Handles logging of connection events, health checks, and system operations.

    Requirements: 25.1, 25.2, 25.3, 25.4
    """

    def log_stream_connected(
        self,
        account: OandaAccount,
        stream_type: str,
        instrument: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a stream connection event.

        Requirements: 25.1
        """
        details = {
            "stream_type": stream_type,
            "account_id": account.account_id,
            "instrument": instrument,
            **kwargs,
        }
        return self.log_event(
            category="system",
            event_type="stream_connected",
            description=f"{stream_type} stream connected for account {account.account_id}",
            severity="info",
            account=account,
            details=details,
        )

    def log_stream_disconnected(
        self,
        account: OandaAccount,
        stream_type: str,
        reason: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a stream disconnection event.

        Requirements: 25.1
        """
        details = {
            "stream_type": stream_type,
            "account_id": account.account_id,
            "reason": reason,
            **kwargs,
        }
        severity = "warning" if reason else "info"
        desc = f"{stream_type} stream disconnected for account " f"{account.account_id}"
        if reason:
            desc += f": {reason}"
        return self.log_event(
            category="system",
            event_type="stream_disconnected",
            description=desc,
            severity=severity,
            account=account,
            details=details,
        )

    def log_stream_reconnection_attempt(
        self,
        account: OandaAccount,
        stream_type: str,
        attempt_number: int,
        **kwargs: Any,
    ) -> Event:
        """
        Log a stream reconnection attempt.

        Requirements: 25.1
        """
        details = {
            "stream_type": stream_type,
            "account_id": account.account_id,
            "attempt_number": attempt_number,
            **kwargs,
        }
        desc = (
            f"Reconnection attempt #{attempt_number} for {stream_type} "
            f"stream (account {account.account_id})"
        )
        return self.log_event(
            category="system",
            event_type="stream_reconnection_attempt",
            description=desc,
            severity="warning",
            account=account,
            details=details,
        )

    def log_database_connection_failure(
        self,
        error_message: str,
        **kwargs: Any,
    ) -> Event:
        """
        Log a database connection failure.

        Requirements: 25.2
        """
        details = {
            "error_message": error_message,
            **kwargs,
        }
        return self.log_event(
            category="system",
            event_type="database_connection_failure",
            description=f"Database connection failed: {error_message}",
            severity="critical",
            details=details,
        )

    def log_database_reconnected(self, **kwargs: Any) -> Event:
        """
        Log a database reconnection.

        Requirements: 25.2
        """
        return self.log_event(
            category="system",
            event_type="database_reconnected",
            description="Database connection restored",
            severity="info",
            details=kwargs,
        )

    def log_redis_connection_failure(
        self,
        error_message: str,
        **kwargs: Any,
    ) -> Event:
        """
        Log a Redis connection failure.

        Requirements: 25.3
        """
        details = {
            "error_message": error_message,
            **kwargs,
        }
        return self.log_event(
            category="system",
            event_type="redis_connection_failure",
            description=f"Redis connection failed: {error_message}",
            severity="error",
            details=details,
        )

    def log_redis_reconnected(self, **kwargs: Any) -> Event:
        """
        Log a Redis reconnection.

        Requirements: 25.3
        """
        return self.log_event(
            category="system",
            event_type="redis_reconnected",
            description="Redis connection restored",
            severity="info",
            details=kwargs,
        )

    def log_celery_task_failure(
        self,
        task_name: str,
        error_message: str,
        stack_trace: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a Celery task failure.

        Requirements: 25.4
        """
        details = {
            "task_name": task_name,
            "error_message": error_message,
            "stack_trace": stack_trace,
            **kwargs,
        }
        return self.log_event(
            category="system",
            event_type="celery_task_failure",
            description=f"Celery task '{task_name}' failed: {error_message}",
            severity="error",
            details=details,
        )

    def log_health_check(
        self,
        status: str,
        metrics: dict[str, Any],
        **kwargs: Any,
    ) -> Event:
        """
        Log a system health check.

        Requirements: 25.4
        """
        details = {
            "status": status,
            "metrics": metrics,
            **kwargs,
        }
        severity = "info" if status == "healthy" else "warning"
        return self.log_event(
            category="system",
            event_type="health_check",
            description=f"System health check: {status}",
            severity=severity,
            details=details,
        )

    def log_container_restart(
        self,
        container_name: str,
        version: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a Docker container restart.

        Requirements: 25.4
        """
        details = {
            "container_name": container_name,
            "version": version,
            **kwargs,
        }
        desc = f"Container '{container_name}' restarted"
        if version:
            desc += f" (version {version})"
        return self.log_event(
            category="system",
            event_type="container_restart",
            description=desc,
            severity="info",
            details=details,
        )


class SecurityEventLogger(EventLogger):
    """
    Specialized logger for security events.

    Handles logging of authentication, authorization, and access events.

    Requirements: 26.1, 26.2, 26.3, 26.4
    """

    def log_login_success(
        self,
        user: "UserType",
        ip_address: str,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a successful login.

        Requirements: 26.1
        """
        return self.log_event(
            category="security",
            event_type="login_success",
            description=f"User '{user.username}' logged in successfully",
            severity="info",
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            details=kwargs,
        )

    def log_login_failed(
        self,
        username: str,
        ip_address: str,
        reason: str,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a failed login attempt.

        Requirements: 26.1
        """
        details = {
            "username": username,
            "reason": reason,
            **kwargs,
        }
        return self.log_event(
            category="security",
            event_type="login_failed",
            description=f"Failed login attempt for '{username}': {reason}",
            severity="warning",
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

    def log_logout(
        self,
        user: "UserType",
        ip_address: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a user logout.

        Requirements: 26.1
        """
        return self.log_event(
            category="security",
            event_type="logout",
            description=f"User '{user.username}' logged out",
            severity="info",
            user=user,
            ip_address=ip_address,
            details=kwargs,
        )

    def log_account_locked(
        self,
        username: str,
        ip_address: str,
        failed_attempts: int,
        **kwargs: Any,
    ) -> Event:
        """
        Log an account lockout.

        Requirements: 26.1
        """
        details = {
            "username": username,
            "failed_attempts": failed_attempts,
            **kwargs,
        }
        desc = f"Account '{username}' locked after {failed_attempts} " f"failed login attempts"
        return self.log_event(
            category="security",
            event_type="account_locked",
            description=desc,
            severity="error",
            ip_address=ip_address,
            details=details,
        )

    def log_ip_blocked(
        self,
        ip_address: str,
        failed_attempts: int,
        duration_seconds: int,
        **kwargs: Any,
    ) -> Event:
        """
        Log an IP address block.

        Requirements: 26.1
        """
        details = {
            "failed_attempts": failed_attempts,
            "duration_seconds": duration_seconds,
            **kwargs,
        }
        desc = (
            f"IP address {ip_address} blocked for {duration_seconds}s "
            f"after {failed_attempts} failed attempts"
        )
        return self.log_event(
            category="security",
            event_type="ip_blocked",
            description=desc,
            severity="warning",
            ip_address=ip_address,
            details=details,
        )

    def log_account_created(
        self,
        username: str,
        email: str,
        ip_address: str,
        **kwargs: Any,
    ) -> Event:
        """
        Log an account creation.

        Requirements: 26.2
        """
        details = {
            "username": username,
            "email": email,
            **kwargs,
        }
        return self.log_event(
            category="security",
            event_type="account_created",
            description=f"New account created: '{username}' ({email})",
            severity="info",
            ip_address=ip_address,
            details=details,
        )

    def log_config_changed(
        self,
        user: "UserType",
        config_type: str,
        changed_parameters: dict[str, Any],
        **kwargs: Any,
    ) -> Event:
        """
        Log a configuration change.

        Requirements: 26.3
        """
        details = {
            "config_type": config_type,
            "changed_parameters": changed_parameters,
            **kwargs,
        }
        return self.log_event(
            category="security",
            event_type="config_changed",
            description=f"Configuration changed by '{user.username}': {config_type}",
            severity="info",
            user=user,
            details=details,
        )

    def log_unauthorized_access_attempt(  # pylint: disable=too-many-positional-arguments
        self,
        user: "UserType | None",
        resource: str,
        ip_address: str,
        **kwargs: Any,
    ) -> Event:
        """
        Log an unauthorized access attempt.

        Requirements: 26.4
        """
        details = {
            "resource": resource,
            **kwargs,
        }
        username = user.username if user else "anonymous"
        desc = f"Unauthorized access attempt by '{username}' to " f"resource: {resource}"
        return self.log_event(
            category="security",
            event_type="unauthorized_access_attempt",
            description=desc,
            severity="warning",
            user=user,
            ip_address=ip_address,
            details=details,
        )

    def log_suspicious_pattern(
        self,
        pattern_type: str,
        description: str,
        ip_address: str | None = None,
        user: "UserType | None" = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a suspicious pattern detection.

        Requirements: 26.4
        """
        details = {
            "pattern_type": pattern_type,
            **kwargs,
        }
        return self.log_event(
            category="security",
            event_type="suspicious_pattern",
            description=f"Suspicious pattern detected: {description}",
            severity="warning",
            user=user,
            ip_address=ip_address,
            details=details,
        )


class AdminEventLogger(EventLogger):
    """
    Specialized logger for admin events.

    Handles logging of admin actions and operations.

    Requirements: 26.2, 26.3, 26.4
    """

    def log_user_kickoff(
        self,
        admin_user: "UserType",
        target_user: "UserType",
        reason: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a user kick-off action.

        Requirements: 26.2
        """
        details = {
            "admin_username": admin_user.username,
            "target_username": target_user.username,
            "reason": reason,
            **kwargs,
        }
        desc = f"Admin '{admin_user.username}' kicked off user " f"'{target_user.username}'"
        if reason:
            desc += f": {reason}"
        return self.log_event(
            category="admin",
            event_type="user_kickoff",
            description=desc,
            severity="warning",
            user=admin_user,
            details=details,
        )

    def log_strategy_stopped_by_admin(  # pylint: disable=too-many-positional-arguments
        self,
        admin_user: "UserType",
        target_user: "UserType",
        account: OandaAccount,
        strategy_name: str,
        reason: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log an admin strategy stop action.

        Requirements: 26.2
        """
        details = {
            "admin_username": admin_user.username,
            "target_username": target_user.username,
            "strategy_name": strategy_name,
            "reason": reason,
            **kwargs,
        }
        desc = (
            f"Admin '{admin_user.username}' stopped strategy "
            f"'{strategy_name}' for user '{target_user.username}'"
        )
        if reason:
            desc += f": {reason}"
        return self.log_event(
            category="admin",
            event_type="strategy_stopped_by_admin",
            description=desc,
            severity="warning",
            user=admin_user,
            account=account,
            details=details,
        )

    def log_system_settings_changed(  # pylint: disable=too-many-positional-arguments
        self,
        admin_user: "UserType",
        setting_name: str,
        old_value: Any,
        new_value: Any,
        **kwargs: Any,
    ) -> Event:
        """
        Log a system settings change.

        Requirements: 26.3
        """
        details = {
            "setting_name": setting_name,
            "old_value": old_value,
            "new_value": new_value,
            **kwargs,
        }
        desc = (
            f"Admin '{admin_user.username}' changed system setting "
            f"'{setting_name}' from '{old_value}' to '{new_value}'"
        )
        return self.log_event(
            category="admin",
            event_type="system_settings_changed",
            description=desc,
            severity="info",
            user=admin_user,
            details=details,
        )

    def log_deployment(
        self,
        version: str,
        deployed_by: str | None = None,
        **kwargs: Any,
    ) -> Event:
        """
        Log a deployment event.

        Requirements: 26.4
        """
        details = {
            "version": version,
            "deployed_by": deployed_by,
            **kwargs,
        }
        desc = f"System deployed: version {version}"
        if deployed_by:
            desc += f" by {deployed_by}"
        return self.log_event(
            category="admin",
            event_type="deployment",
            description=desc,
            severity="info",
            details=details,
        )
