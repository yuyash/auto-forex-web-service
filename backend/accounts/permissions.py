"""
Permission classes for role-based access control.

This module provides permission classes for restricting access to admin-only
endpoints.

Requirements: 19.5, 20.5, 21.5, 22.5, 23.5, 27.5, 28.5, 33.4, 37.5
"""

from typing import Optional

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class IsAdminUser(permissions.BasePermission):
    """
    Permission class that allows access only to admin users.

    Admin users are identified by the is_staff flag on the User model.
    This permission should be used for all admin-only endpoints.

    Requirements: 19.5, 20.5, 21.5, 22.5, 23.5, 27.5, 28.5, 33.4, 37.5
    """

    message = "You do not have permission to access this resource."

    def has_permission(self, request: Request, view: Optional[APIView]) -> bool:
        """
        Check if the user has admin permissions.

        Args:
            request: HTTP request
            view: API view being accessed

        Returns:
            True if user is authenticated and is_staff, False otherwise
        """
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # User must be active
        if not request.user.is_active:
            return False

        # User must be staff (admin)
        return bool(request.user.is_staff)


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission class that allows read-only access to all users,
    but write access only to admin users.

    Requirements: 19.5, 20.5, 21.5, 22.5, 23.5
    """

    message = "You do not have permission to modify this resource."

    def has_permission(self, request: Request, view: Optional[APIView]) -> bool:
        """
        Check if the user has permission for the requested action.

        Args:
            request: HTTP request
            view: API view being accessed

        Returns:
            True if read-only request or user is admin, False otherwise
        """
        # User must be authenticated and active
        if not request.user or not request.user.is_authenticated:
            return False

        if not request.user.is_active:
            return False

        # Allow read-only methods for all authenticated active users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write methods require admin privileges
        return bool(request.user.is_staff)
