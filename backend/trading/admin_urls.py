"""
Admin dashboard URL configuration.

This module defines URL patterns for admin-only endpoints.

Requirements: 19.1-19.5, 20.1-20.5, 21.1-21.5, 22.1-22.5, 23.1-23.5, 28.1-28.5, 37.1-37.5
"""

from django.urls import path

from trading import admin_views

app_name = "trading_admin"

urlpatterns = [
    # System health monitoring
    path("health/", admin_views.get_system_health, name="system-health"),
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
]
