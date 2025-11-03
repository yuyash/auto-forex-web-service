"""
WebSocket routing configuration for Django Channels.

This module defines the WebSocket URL patterns for real-time communication.
"""

from django.urls import path

from trading.consumers import AdminNotificationConsumer, MarketDataConsumer, PositionUpdateConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    path("ws/market-data/<str:account_id>/", MarketDataConsumer.as_asgi()),
    path("ws/positions/<str:account_id>/", PositionUpdateConsumer.as_asgi()),
    path("ws/admin/notifications/", AdminNotificationConsumer.as_asgi()),
]
