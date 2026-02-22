"""Views for user authentication and management."""

from .login import UserLoginView
from .logout import UserLogoutView
from .notifications import (
    UserNotificationListView,
    UserNotificationMarkAllReadView,
    UserNotificationMarkReadView,
)
from .refresh import TokenRefreshView
from .registration import UserRegistrationView
from .settings import PublicAccountSettingsView, UserSettingsView
from .verification import EmailVerificationView, ResendVerificationEmailView

__all__ = [
    "EmailVerificationView",
    "PublicAccountSettingsView",
    "ResendVerificationEmailView",
    "TokenRefreshView",
    "UserLoginView",
    "UserLogoutView",
    "UserNotificationListView",
    "UserNotificationMarkAllReadView",
    "UserNotificationMarkReadView",
    "UserRegistrationView",
    "UserSettingsView",
]
