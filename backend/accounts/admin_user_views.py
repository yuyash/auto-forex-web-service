"""
Admin user management views.

This module provides admin-only endpoints for:
- Listing all users
- Creating new users
- Deleting users
- Updating user details
"""

import logging
from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Empty, Request
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminUser
from trading.event_logger import EventLogger

logger = logging.getLogger(__name__)


def _get_admin_user(user_obj: Any) -> User | None:
    """Return the authenticated User instance when available."""
    if isinstance(user_obj, User):
        return user_obj
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def list_users(request: Request) -> Response:
    """
    Get list of all users with their details.

    Query parameters:
    - search: Search by username or email
    - is_active: Filter by active status (true/false)
    - is_staff: Filter by staff status (true/false)
    - ordering: Order by field (username, email, date_joined, last_login)

    Args:
        request: HTTP request object

    Returns:
        Response with list of users
    """
    try:
        # Get query parameters
        search = request.query_params.get("search", "").strip()
        is_active = request.query_params.get("is_active")
        is_staff = request.query_params.get("is_staff")
        ordering = request.query_params.get("ordering", "-date_joined")

        # Build query
        users = User.objects.all()

        # Apply filters
        if search:
            users = users.filter(username__icontains=search) | users.filter(email__icontains=search)

        if is_active is not None:
            users = users.filter(is_active=is_active.lower() == "true")

        if is_staff is not None:
            users = users.filter(is_staff=is_staff.lower() == "true")

        # Apply ordering
        valid_orderings = [
            "username",
            "-username",
            "email",
            "-email",
            "date_joined",
            "-date_joined",
            "last_login",
            "-last_login",
        ]
        if ordering in valid_orderings:
            users = users.order_by(ordering)

        # Serialize user data
        users_data = [
            {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "date_joined": user.date_joined.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "failed_login_attempts": user.failed_login_attempts,
                "is_locked": user.is_locked,
            }
            for user in users
        ]

        return Response(
            {
                "count": len(users_data),
                "users": users_data,
                "timestamp": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error("Failed to list users: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to retrieve users"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminUser])
def create_user(request: Request) -> Response:
    """
    Create a new user.

    Required fields:
    - username: Unique username
    - email: Unique email address
    - password: User password

    Optional fields:
    - first_name: User's first name
    - last_name: User's last name
    - is_staff: Admin privileges (default: false)
    - is_active: Account active status (default: true)

    Args:
        request: HTTP request object

    Returns:
        Response with created user data
    """
    try:
        # Get request data with Empty sentinel safety for type checkers
        raw_data: Any = request.data
        data: Mapping[str, Any]
        if raw_data is Empty:
            data = {}
        else:
            data = cast(Mapping[str, Any], raw_data)

        # Validate required fields
        required_fields = ["username", "email", "password"]
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = data["username"].strip()
        email = data["email"].strip().lower()
        password = data["password"]

        # Validate username and email uniqueness
        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "Email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create user
        with transaction.atomic():
            user = User.objects.create(
                username=username,
                email=email,
                password=make_password(password),
                first_name=data.get("first_name", "").strip(),
                last_name=data.get("last_name", "").strip(),
                is_staff=data.get("is_staff", False),
                is_active=data.get("is_active", True),
            )

            # Log the creation event
            event_logger = EventLogger()
            admin_user = _get_admin_user(request.user)
            admin_email = admin_user.email if admin_user else "unknown"
            event_logger.log_event(
                category="admin",
                event_type="user_created",
                severity="info",
                description=f"Admin {admin_email} created user {user.email}",
                details={
                    "admin_user_id": request.user.pk,
                    "admin_email": admin_email,
                    "created_user_id": user.pk,
                    "created_email": user.email,
                    "created_username": user.username,
                    "is_staff": user.is_staff,
                },
                user=admin_user if admin_user else None,
            )

            logger.info("Admin %s created user %s (ID: %d)", admin_email, user.email, user.pk)

        # Return created user data
        user_data = {
            "id": user.pk,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "date_joined": user.date_joined.isoformat(),
        }

        return Response(
            {"message": "User created successfully", "user": user_data},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error("Failed to create user: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to create user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsAdminUser])
def delete_user(request: Request, user_id: int) -> Response:
    """
    Delete a user.

    This endpoint permanently deletes a user and all associated data.
    Superusers cannot be deleted.

    Args:
        request: HTTP request object
        user_id: ID of the user to delete

    Returns:
        Response indicating success or failure
    """
    try:
        # Get the target user
        target_user = User.objects.get(id=user_id)

        # Prevent deletion of superusers
        if target_user.is_superuser:
            return Response(
                {"error": "Cannot delete superuser accounts"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Prevent self-deletion
        if target_user.pk == request.user.pk:
            return Response(
                {"error": "Cannot delete your own account"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Store user info for logging
        deleted_email = target_user.email
        deleted_username = target_user.username

        # Delete the user
        with transaction.atomic():
            target_user.delete()

            # Log the deletion event
            event_logger = EventLogger()
            admin_user = _get_admin_user(request.user)
            admin_email = admin_user.email if admin_user else "unknown"
            event_logger.log_event(
                category="admin",
                event_type="user_deleted",
                severity="warning",
                description=f"Admin {admin_email} deleted user {deleted_email}",
                details={
                    "admin_user_id": request.user.pk,
                    "admin_email": admin_email,
                    "deleted_user_id": user_id,
                    "deleted_email": deleted_email,
                    "deleted_username": deleted_username,
                },
                user=admin_user if admin_user else None,
            )

            logger.warning(
                "Admin %s deleted user %s (ID: %d)",
                admin_email,
                deleted_email,
                user_id,
            )

        return Response(
            {
                "message": f"User {deleted_email} has been deleted",
                "deleted_user_id": user_id,
            },
            status=status.HTTP_200_OK,
        )

    except User.DoesNotExist:
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error("Failed to delete user: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to delete user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_user(request: Request, user_id: int) -> Response:
    """
    Update user details.

    Updatable fields:
    - first_name: User's first name
    - last_name: User's last name
    - is_active: Account active status
    - is_staff: Admin privileges
    - is_locked: Account lock status

    Args:
        request: HTTP request object
        user_id: ID of the user to update

    Returns:
        Response with updated user data
    """
    try:
        # Get the target user
        target_user = User.objects.get(id=user_id)

        # Get request data with Empty sentinel safety for type checkers
        raw_data: Any = request.data
        data: Mapping[str, Any]
        if raw_data is Empty:
            data = {}
        else:
            data = cast(Mapping[str, Any], raw_data)

        # Update allowed fields
        updated_fields = []

        if "first_name" in data:
            target_user.first_name = data["first_name"].strip()
            updated_fields.append("first_name")

        if "last_name" in data:
            target_user.last_name = data["last_name"].strip()
            updated_fields.append("last_name")

        if "is_active" in data:
            target_user.is_active = bool(data["is_active"])
            updated_fields.append("is_active")

        if "is_staff" in data:
            # Prevent removing superuser's staff status
            if target_user.is_superuser and not data["is_staff"]:
                return Response(
                    {"error": "Cannot remove staff status from superuser"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            target_user.is_staff = bool(data["is_staff"])
            updated_fields.append("is_staff")

        if "is_locked" in data:
            target_user.is_locked = bool(data["is_locked"])
            if not target_user.is_locked:
                target_user.failed_login_attempts = 0
            updated_fields.append("is_locked")

        # Save changes
        if updated_fields:
            target_user.save(update_fields=updated_fields)

            # Log the update event
            event_logger = EventLogger()
            admin_user = _get_admin_user(request.user)
            admin_email = admin_user.email if admin_user else "unknown"
            event_logger.log_event(
                category="admin",
                event_type="user_updated",
                severity="info",
                description=f"Admin {admin_email} updated user {target_user.email}",
                details={
                    "admin_user_id": request.user.pk,
                    "admin_email": admin_email,
                    "updated_user_id": target_user.pk,
                    "updated_email": target_user.email,
                    "updated_fields": updated_fields,
                },
                user=admin_user if admin_user else None,
            )

            logger.info(
                "Admin %s updated user %s (fields: %s)",
                admin_email,
                target_user.email,
                ", ".join(updated_fields),
            )

        # Return updated user data
        user_data = {
            "id": target_user.pk,
            "username": target_user.username,
            "email": target_user.email,
            "first_name": target_user.first_name,
            "last_name": target_user.last_name,
            "is_active": target_user.is_active,
            "is_staff": target_user.is_staff,
            "is_superuser": target_user.is_superuser,
            "is_locked": target_user.is_locked,
            "failed_login_attempts": target_user.failed_login_attempts,
            "date_joined": target_user.date_joined.isoformat(),
            "last_login": target_user.last_login.isoformat() if target_user.last_login else None,
        }

        return Response(
            {
                "message": "User updated successfully",
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

    except User.DoesNotExist:
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error("Failed to update user: %s", e, exc_info=True)
        return Response(
            {"error": "Failed to update user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
