"""
Admin dashboard URL configuration.

This module defines URL patterns for admin-only endpoints.

Requirements: 19.1-19.5, 20.1-20.5, 21.1-21.5, 22.1-22.5, 23.1-23.5, 28.1-28.5, 37.1-37.5
"""

from django.urls import path

from accounts import admin_user_views
from trading import admin_views

app_name = "trading_admin"

urlpatterns = [
    # System health monitoring
    path("health/", admin_views.get_system_health, name="system-health"),
    # User management
    path("users/", admin_user_views.list_users, name="list-users"),
    path("users/create/", admin_user_views.create_user, name="create-user"),
    path("users/<int:user_id>/", admin_user_views.update_user, name="update-user"),
    path("users/<int:user_id>/delete/", admin_user_views.delete_user, name="delete-user"),
    # User session management
    path("users/online/", admin_views.get_online_users, name="online-users"),
    path("users/<int:user_id>/kickoff/", admin_views.kickoff_user, name="kickoff-user"),
    # Strategy monitoring and control
    path("strategies/running/", admin_views.get_running_strategies, name="running-strategies"),
    path("strategies/<int:strategy_id>/stop/", admin_views.stop_strategy, name="stop-strategy"),
    # Dashboard aggregation
    path("dashboard/", admin_views.get_admin_dashboard, name="dashboard"),
    # Security monitoring
    path("security/", admin_views.get_security_dashboard, name="security-dashboard"),
    # Notification management
    path("notifications", admin_views.get_notifications, name="notifications"),
    path(
        "notifications/<int:notification_id>/read",
        admin_views.mark_notification_read,
        name="notification-read",
    ),
    path(
        "notifications/read-all",
        admin_views.mark_all_notifications_read,
        name="notifications-read-all",
    ),
]
