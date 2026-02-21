"""Accounts service layer.

Service modules that encapsulate side-effecting operations like email sending,
JWT handling, and security event persistence.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .email import AccountEmailService
    from .events import SecurityEventService
    from .jwt import JWTService

__all__: List[str] = [
    "AccountEmailService",
    "JWTService",
    "SecurityEventService",
]
