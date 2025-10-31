"""
WebSocket routing configuration for Django Channels.

This module defines the WebSocket URL patterns for real-time communication.
"""

from typing import Any

# from django.urls import path

# WebSocket URL patterns will be added here as consumers are created
websocket_urlpatterns: list[Any] = [
    # path('ws/market-data/<str:account_id>/', MarketDataConsumer.as_asgi()),
    # path('ws/admin/notifications/', AdminNotificationConsumer.as_asgi()),
]
