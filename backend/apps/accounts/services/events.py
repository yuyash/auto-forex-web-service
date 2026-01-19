"""Security event service for logging authentication and security events."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from apps.accounts.models import AccountSecurityEvent, User


class EventSeverity(str, Enum):
    """Security event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(str, Enum):
    """Security event types."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_CREATED = "account_created"
    IP_BLOCKED = "ip_blocked"
    CONFIG_CHANGED = "config_changed"
    UNAUTHORIZED_ACCESS = "unauthorized_access_attempt"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


@dataclass(frozen=True)
class SecurityEvent:
    """Immutable security event data object."""

    event_type: EventType
    description: str
    severity: EventSeverity = EventSeverity.INFO
    user: User | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for database storage."""
        return {
            "event_type": self.event_type.value,
            "category": "security",
            "severity": self.severity.value,
            "description": self.description,
            "user": self.user if self.user and hasattr(self.user, "pk") else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent or "",
            "details": self.details or {},
        }


class SecurityEventService:
    """Service for logging security events to the database."""

    def __init__(self) -> None:
        """Initialize the security event service."""
        pass

    def log_event(self, event: SecurityEvent) -> None:
        """
        Persist a security event to the database.

        Args:
            event: SecurityEvent object to persist
        """
        try:
            AccountSecurityEvent.objects.create(**event.to_dict())
        except Exception:  # pylint: disable=broad-exception-caught
            # Never break request handling due to logging failures
            pass

    def log_login_success(
        self,
        user: User,
        ip_address: str,
        user_agent: str | None = None,
    ) -> None:
        """Log a successful login event."""
        event = SecurityEvent(
            event_type=EventType.LOGIN_SUCCESS,
            description=f"User '{user.username}' logged in successfully",
            severity=EventSeverity.INFO,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.log_event(event)

    def log_login_failed(
        self,
        username: str,
        ip_address: str,
        reason: str,
        user_agent: str | None = None,
    ) -> None:
        """Log a failed login attempt."""
        event = SecurityEvent(
            event_type=EventType.LOGIN_FAILED,
            description=f"Failed login attempt for '{username}': {reason}",
            severity=EventSeverity.WARNING,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"username": username, "reason": reason},
        )
        self.log_event(event)

    def log_logout(
        self,
        user: User,
        ip_address: str | None = None,
    ) -> None:
        """Log a user logout event."""
        event = SecurityEvent(
            event_type=EventType.LOGOUT,
            description=f"User '{user.username}' logged out",
            severity=EventSeverity.INFO,
            user=user,
            ip_address=ip_address,
        )
        self.log_event(event)

    def log_account_locked(
        self,
        username: str,
        ip_address: str,
        failed_attempts: int,
    ) -> None:
        """Log an account lockout event."""
        event = SecurityEvent(
            event_type=EventType.ACCOUNT_LOCKED,
            description=f"Account '{username}' locked after {failed_attempts} failed login attempts",
            severity=EventSeverity.ERROR,
            ip_address=ip_address,
            details={"username": username, "failed_attempts": failed_attempts},
        )
        self.log_event(event)

    def log_ip_blocked(
        self,
        ip_address: str,
        failed_attempts: int,
        duration_seconds: int,
    ) -> None:
        """Log an IP address block event."""
        event = SecurityEvent(
            event_type=EventType.IP_BLOCKED,
            description=(
                f"IP address {ip_address} blocked for {duration_seconds}s "
                f"after {failed_attempts} failed attempts"
            ),
            severity=EventSeverity.WARNING,
            ip_address=ip_address,
            details={"failed_attempts": failed_attempts, "duration_seconds": duration_seconds},
        )
        self.log_event(event)

    def log_account_created(
        self,
        username: str,
        email: str,
        ip_address: str,
    ) -> None:
        """Log an account creation event."""
        event = SecurityEvent(
            event_type=EventType.ACCOUNT_CREATED,
            description=f"New account created: '{username}' ({email})",
            severity=EventSeverity.INFO,
            ip_address=ip_address,
            details={"username": username, "email": email},
        )
        self.log_event(event)

    def log_config_changed(
        self,
        user: User,
        config_type: str,
        changed_parameters: dict[str, Any],
    ) -> None:
        """Log a configuration change event."""
        event = SecurityEvent(
            event_type=EventType.CONFIG_CHANGED,
            description=f"Configuration changed by '{user.username}': {config_type}",
            severity=EventSeverity.INFO,
            user=user,
            details={"config_type": config_type, "changed_parameters": changed_parameters},
        )
        self.log_event(event)

    def log_unauthorized_access_attempt(
        self,
        resource: str,
        ip_address: str,
        user: User | None = None,
    ) -> None:
        """Log an unauthorized access attempt."""
        username = user.username if user else "anonymous"
        event = SecurityEvent(
            event_type=EventType.UNAUTHORIZED_ACCESS,
            description=f"Unauthorized access attempt by '{username}' to resource: {resource}",
            severity=EventSeverity.WARNING,
            user=user,
            ip_address=ip_address,
            details={"resource": resource},
        )
        self.log_event(event)

    def log_suspicious_pattern(
        self,
        pattern_type: str,
        description: str,
        ip_address: str | None = None,
        user: User | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a suspicious pattern detection."""
        event = SecurityEvent(
            event_type=EventType.SUSPICIOUS_PATTERN,
            description=f"Suspicious pattern detected: {description}",
            severity=EventSeverity.WARNING,
            user=user,
            ip_address=ip_address,
            details={"pattern_type": pattern_type, **(details or {})},
        )
        self.log_event(event)

    def log_security_event(
        self,
        event_type: str,
        description: str,
        severity: str = "info",
        user: User | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a generic security event (for backward compatibility)."""
        try:
            event_type_enum = EventType(event_type)
        except ValueError:
            # If event_type is not in enum, use it as-is
            event_type_enum = event_type  # type: ignore[assignment]

        try:
            severity_enum = EventSeverity(severity)
        except ValueError:
            severity_enum = EventSeverity.INFO

        event = SecurityEvent(
            event_type=event_type_enum,  # type: ignore[arg-type]
            description=description,
            severity=severity_enum,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        self.log_event(event)
