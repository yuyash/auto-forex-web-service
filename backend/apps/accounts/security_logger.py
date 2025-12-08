"""
Security event signals for the accounts app.

This module defines Django signals for security events that can be
received by other apps (like the events app) for logging purposes.

This approach decouples the accounts app from the events app.
"""

from typing import Any

import django.dispatch

# Define security event signals
security_event = django.dispatch.Signal()
"""
Signal sent when a security event occurs.

Provides:
    sender: The class sending the signal (SecurityEventLogger)
    event_type: Type of security event (e.g., 'login_success', 'login_failed')
    category: Always 'security' for security events
    description: Human-readable event description
    severity: Event severity (debug, info, warning, error, critical)
    user: User associated with the event (optional)
    ip_address: IP address associated with the event (optional)
    user_agent: User agent string (optional)
    details: Additional event details as dictionary (optional)
"""


class SecurityEventLogger:
    """
    Security event logger that sends signals instead of directly creating Event records.

    This decouples the accounts app from the events app by using Django signals.
    The events app can register receivers to handle these signals and create
    Event records as needed.
    """

    def _send_event(
        self,
        event_type: str,
        description: str,
        severity: str = "info",
        user: Any = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a security event signal.

        Args:
            event_type: Type of security event
            description: Human-readable event description
            severity: Event severity (debug, info, warning, error, critical)
            user: User associated with the event
            ip_address: IP address associated with the event
            user_agent: User agent string
            details: Additional event details as dictionary
        """
        security_event.send(
            sender=self.__class__,
            event_type=event_type,
            category="security",
            description=description,
            severity=severity,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )

    def log_login_success(
        self,
        user: Any,
        ip_address: str,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a successful login."""
        self._send_event(
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
    ) -> None:
        """Log a failed login attempt."""
        details = {
            "username": username,
            "reason": reason,
            **kwargs,
        }
        self._send_event(
            event_type="login_failed",
            description=f"Failed login attempt for '{username}': {reason}",
            severity="warning",
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

    def log_logout(
        self,
        user: Any,
        ip_address: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a user logout."""
        self._send_event(
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
    ) -> None:
        """Log an account lockout."""
        details = {
            "username": username,
            "failed_attempts": failed_attempts,
            **kwargs,
        }
        desc = f"Account '{username}' locked after {failed_attempts} failed login attempts"
        self._send_event(
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
    ) -> None:
        """Log an IP address block."""
        details = {
            "failed_attempts": failed_attempts,
            "duration_seconds": duration_seconds,
            **kwargs,
        }
        desc = (
            f"IP address {ip_address} blocked for {duration_seconds}s "
            f"after {failed_attempts} failed attempts"
        )
        self._send_event(
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
    ) -> None:
        """Log an account creation."""
        details = {
            "username": username,
            "email": email,
            **kwargs,
        }
        self._send_event(
            event_type="account_created",
            description=f"New account created: '{username}' ({email})",
            severity="info",
            ip_address=ip_address,
            details=details,
        )

    def log_config_changed(
        self,
        user: Any,
        config_type: str,
        changed_parameters: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Log a configuration change."""
        details = {
            "config_type": config_type,
            "changed_parameters": changed_parameters,
            **kwargs,
        }
        self._send_event(
            event_type="config_changed",
            description=f"Configuration changed by '{user.username}': {config_type}",
            severity="info",
            user=user,
            details=details,
        )

    def log_unauthorized_access_attempt(
        self,
        user: Any | None,
        resource: str,
        ip_address: str,
        **kwargs: Any,
    ) -> None:
        """Log an unauthorized access attempt."""
        details = {
            "resource": resource,
            **kwargs,
        }
        username = user.username if user else "anonymous"
        desc = f"Unauthorized access attempt by '{username}' to resource: {resource}"
        self._send_event(
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
        user: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a suspicious pattern detection."""
        details = {
            "pattern_type": pattern_type,
            **kwargs,
        }
        self._send_event(
            event_type="suspicious_pattern",
            description=f"Suspicious pattern detected: {description}",
            severity="warning",
            user=user,
            ip_address=ip_address,
            details=details,
        )

    def log_security_event(
        self,
        event_type: str,
        description: str,
        severity: str = "info",
        user: Any | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a generic security event.

        This is a generic method for logging security events that don't fit
        into the more specific methods above.

        Args:
            event_type: Type of security event
            description: Human-readable event description
            severity: Event severity (debug, info, warning, error, critical)
            user: User associated with the event
            ip_address: IP address associated with the event
            user_agent: User agent string
            details: Additional event details as dictionary
        """
        self._send_event(
            event_type=event_type,
            description=description,
            severity=severity,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
