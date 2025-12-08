"""
WebSocket routing configuration for Django Channels.

This module defines the WebSocket URL patterns for real-time communication.
"""

# pylint: disable=cyclic-import

# from django.urls import path

# WebSocket URL patterns
# Note: Market-related consumers are disabled until apps.market is enabled
websocket_urlpatterns: list = [
    # Uncomment when apps.market is enabled in INSTALLED_APPS:
    # path("ws/market-data/<str:account_id>/<str:instrument>/", MarketDataConsumer.as_asgi()),
    # path("ws/positions/<str:account_id>/", PositionUpdateConsumer.as_asgi()),
    # path("ws/admin/notifications/", AdminNotificationConsumer.as_asgi()),
    # path("ws/admin/dashboard/", AdminDashboardConsumer.as_asgi()),
]
