"""
Views for user authentication and management.

This module contains views for:
- User registration
- User login
- User logout
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserRegistrationSerializer


class UserRegistrationView(APIView):
    """
    API endpoint for user registration.

    POST /api/auth/register
    - Register a new user account
    - Send verification email (placeholder)

    Requirements: 1.1, 1.2, 1.3, 1.5
    """

    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def post(self, request: Request) -> Response:
        """
        Handle user registration.

        Args:
            request: HTTP request with email, username, password, password_confirm

        Returns:
            Response with user data or validation errors
        """
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # Placeholder for future email verification implementation
            # send_verification_email(user)

            return Response(
                {
                    "message": (
                        "User registered successfully. " "Please check your email for verification."
                    ),
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
