"""
JWT token generation and validation utilities.

This module provides utilities for:
- JWT token generation
- JWT token validation
- Token refresh

Requirements: 2.3, 2.4
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth import get_user_model

import jwt  # pylint: disable=import-error

User = get_user_model()


def generate_jwt_token(user: Any) -> str:
    """
    Generate a JWT token for the given user.

    Args:
        user: User instance

    Returns:
        JWT token string

    Requirements: 2.3
    """
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(seconds=settings.JWT_EXPIRATION_DELTA)

    payload = {
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "is_staff": user.is_staff,
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    if isinstance(token, memoryview):  # normalize memoryview to bytes before decoding
        token = token.tobytes()

    if isinstance(token, (bytes, bytearray)):
        token_str = token.decode("utf-8")
    else:
        token_str = token

    return token_str


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dictionary or None if invalid

    Requirements: 2.4
    """
    try:
        payload: Dict[str, Any] = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_from_token(token: str) -> Optional[Any]:
    """
    Get user instance from JWT token.

    Args:
        token: JWT token string

    Returns:
        User instance or None if token is invalid

    Requirements: 2.4
    """
    payload = decode_jwt_token(token)
    if not payload:
        return None

    try:
        user = User.objects.get(id=payload["user_id"])
        return user
    except User.DoesNotExist:
        return None


def refresh_jwt_token(token: str) -> Optional[str]:
    """
    Refresh a JWT token if it's valid.

    Args:
        token: JWT token string

    Returns:
        New JWT token string or None if token is invalid

    Requirements: 2.3, 2.4
    """
    user = get_user_from_token(token)
    if not user:
        return None

    if not user.is_active:
        return None

    if user.is_locked:
        return None

    # Generate new token
    new_token = generate_jwt_token(user)
    return new_token
