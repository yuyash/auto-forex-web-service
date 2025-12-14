"""apps.accounts.services.events

Accounts-owned security/auth events.

Accounts must be self-contained: security/auth events are persisted to the
database via the AccountSecurityEvent model.
"""

from typing import Any

from apps.accounts.models import AccountSecurityEvent


class SecurityEventService:
    """Security event service that persists AccountSecurityEvent records."""

    def _write_event(
        self,
        event_type: str,
        description: str,
        severity: str = "info",
        user: Any = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Persist a security event.

        This method is intentionally side-effect-only and does not raise.
        """

        try:
            AccountSecurityEvent.objects.create(
                event_type=event_type,
                category="security",
                severity=severity,
                description=description,
                user=user if getattr(user, "pk", None) else None,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details or {},
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # Never break request handling due to logging failures.
            return

    def log_login_success(
        self,
        user: Any,
        ip_address: str,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a successful login."""
        self._write_event(
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
        self._write_event(
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
        self._write_event(
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
        self._write_event(
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
        self._write_event(
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
        self._write_event(
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
        self._write_event(
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
        self._write_event(
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
        self._write_event(
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
        """Log a generic security event."""
        self._write_event(
            event_type=event_type,
            description=description,
            severity=severity,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
