"""User notification views."""

import logging

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserNotification

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        summary="List user notifications",
        description="Retrieve list of notifications for the authenticated user. "
        "Supports filtering by read status and limiting results.",
        parameters=[
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of notifications to return (1-200, default: 50)",
                required=False,
            ),
            OpenApiParameter(
                name="unread_only",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter to show only unread notifications",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Notifications retrieved successfully",
                response={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "title": {"type": "string"},
                            "message": {"type": "string"},
                            "severity": {
                                "type": "string",
                                "enum": ["info", "warning", "error", "critical"],
                            },
                            "timestamp": {"type": "string", "format": "date-time"},
                            "read": {"type": "boolean"},
                            "notification_type": {"type": "string"},
                            "extra_data": {"type": "object"},
                        },
                    },
                },
            ),
            401: OpenApiResponse(description="Authentication required"),
            500: OpenApiResponse(description="Failed to retrieve notifications"),
        },
        tags=["Notifications"],
    )
)
class UserNotificationListView(APIView):
    """List notifications for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """Get list of notifications for the authenticated user."""
        try:
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            limit_raw = request.query_params.get("limit")
            limit = 50
            if limit_raw:
                try:
                    limit = max(1, min(int(limit_raw), 200))
                except ValueError:
                    limit = 50

            unread_only = request.query_params.get("unread_only")
            unread_only_bool = str(unread_only).lower() in {"1", "true", "yes"}

            queryset = UserNotification.objects.filter(user_id=user_id).order_by("-timestamp")
            if unread_only_bool:
                queryset = queryset.filter(is_read=False)

            notifications = list(queryset[:limit])

            data = [
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "severity": n.severity,
                    "timestamp": n.timestamp.isoformat(),
                    "read": n.is_read,
                    "notification_type": n.notification_type,
                    "extra_data": n.extra_data,
                }
                for n in notifications
            ]
            return Response(data, status=status.HTTP_200_OK)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to list user notifications: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to retrieve notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        summary="Mark notification as read",
        description="Mark a single notification as read for the authenticated user.",
        parameters=[
            OpenApiParameter(
                name="notification_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID of the notification to mark as read",
                required=True,
            ),
        ],
        request=None,
        responses={
            200: OpenApiResponse(description="Notification marked as read"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Notification not found"),
            500: OpenApiResponse(description="Failed to mark notification as read"),
        },
        tags=["Notifications"],
    )
)
class UserNotificationMarkReadView(APIView):
    """Mark a single notification as read for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, notification_id: int) -> Response:
        """Mark a notification as read."""
        try:
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            notification = UserNotification.objects.get(id=notification_id, user_id=user_id)
            if not notification.is_read:
                notification.is_read = True
                notification.save(update_fields=["is_read"])

            return Response(
                {"message": "Notification marked as read"},
                status=status.HTTP_200_OK,
            )

        except UserNotification.DoesNotExist:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to mark user notification as read: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to mark notification as read"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        summary="Mark all notifications as read",
        description="Mark all unread notifications as read for the authenticated user.",
        request=None,
        responses={
            200: OpenApiResponse(
                description="All notifications marked as read",
                response={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "count": {"type": "integer"},
                    },
                },
            ),
            401: OpenApiResponse(description="Authentication required"),
            500: OpenApiResponse(description="Failed to mark all notifications as read"),
        },
        tags=["Notifications"],
    )
)
class UserNotificationMarkAllReadView(APIView):
    """Mark all unread notifications as read for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Mark all unread notifications as read."""
        try:
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            count = UserNotification.objects.filter(user_id=user_id, is_read=False).update(
                is_read=True
            )

            return Response(
                {"message": f"{count} notifications marked as read", "count": count},
                status=status.HTTP_200_OK,
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to mark all user notifications as read: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to mark all notifications as read"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
