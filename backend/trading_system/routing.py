"""
WebSocket routing configuration for Django Channels.

This module defines the WebSocket URL patterns for real-time communication.
"""

# pylint: disable=cyclic-import

from django.urls import path

from trading.consumers import (
    AdminDashboardConsumer,
    AdminNotificationConsumer,
    MarketDataConsumer,
    PositionUpdateConsumer,
    TaskLogsConsumer,
    TaskStatusConsumer,
)

# WebSocket URL patterns
websocket_urlpatterns = [
    path("ws/market-data/<str:account_id>/<str:instrument>/", MarketDataConsumer.as_asgi()),
    path("ws/positions/<str:account_id>/", PositionUpdateConsumer.as_asgi()),
    path("ws/tasks/<str:task_type>/<int:task_id>/logs/", TaskLogsConsumer.as_asgi()),
    path("ws/tasks/status/", TaskStatusConsumer.as_asgi()),
    path("ws/admin/notifications/", AdminNotificationConsumer.as_asgi()),
    path("ws/admin/dashboard/", AdminDashboardConsumer.as_asgi()),
]
