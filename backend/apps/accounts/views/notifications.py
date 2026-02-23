"""User notification views."""

from logging import Logger, getLogger

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserNotification
from apps.trading.views.pagination import StandardPagination

logger: Logger = getLogger(name=__name__)


class UserNotificationListView(APIView):
    """List notifications for the authenticated user."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    @extend_schema(
        operation_id="notifications_list",
        tags=["Accounts"],
        parameters=[
            OpenApiParameter(name="unread_only", type=bool, required=False),
        ],
        responses={
            200: inline_serializer(
                "NotificationListResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": inline_serializer(
                        "NotificationItem",
                        fields={
                            "id": serializers.IntegerField(),
                            "title": serializers.CharField(),
                            "message": serializers.CharField(),
                            "severity": serializers.CharField(),
                            "timestamp": serializers.DateTimeField(),
                            "read": serializers.BooleanField(),
                            "notification_type": serializers.CharField(),
                            "extra_data": serializers.DictField(allow_null=True),
                        },
                        many=True,
                    ),
                },
            ),
        },
        description="List notifications for the authenticated user.",
    )
    def get(self, request: Request) -> Response:
        """Get list of notifications for the authenticated user."""
        try:
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            unread_only = request.query_params.get("unread_only")
            unread_only_bool = str(unread_only).lower() in {"1", "true", "yes"}

            queryset = UserNotification.objects.filter(user_id=user_id).order_by("-timestamp")
            if unread_only_bool:
                queryset = queryset.filter(is_read=False)

            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)

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
                for n in page
            ]
            return paginator.get_paginated_response(data)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to list user notifications: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to retrieve notifications"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserNotificationMarkReadView(APIView):
    """Mark a single notification as read for the authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="notification_mark_read",
        tags=["Accounts"],
        request=None,
        responses={
            200: inline_serializer(
                "NotificationMarkReadResponse",
                fields={"message": serializers.CharField()},
            ),
            404: inline_serializer(
                "NotificationNotFound",
                fields={"error": serializers.CharField()},
            ),
        },
        description="Mark a single notification as read.",
    )
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


class UserNotificationMarkAllReadView(APIView):
    """Mark all unread notifications as read for the authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="notifications_mark_all_read",
        tags=["Accounts"],
        request=None,
        responses={
            200: inline_serializer(
                "NotificationMarkAllReadResponse",
                fields={
                    "message": serializers.CharField(),
                    "count": serializers.IntegerField(),
                },
            ),
        },
        description="Mark all unread notifications as read.",
    )
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
