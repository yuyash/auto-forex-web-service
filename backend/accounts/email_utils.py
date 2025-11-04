"""
Email utilities for sending verification and notification emails.

This module contains utilities for:
- Sending email verification emails
- Sending password reset emails
- Sending notification emails

Requirements: 1.4, 1.5
"""

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

if TYPE_CHECKING:
    from accounts.models import User

logger = logging.getLogger(__name__)


def send_verification_email(user: "User", verification_url: str) -> bool:
    """
    Send email verification email to user.

    Args:
        user: User instance
        verification_url: Full URL for email verification

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        subject = "Verify your email address - Auto Forex Trading System"

        # HTML email content
        html_message = render_to_string(
            "accounts/emails/verification_email.html",
            {
                "user": user,
                "verification_url": verification_url,
                "site_name": "Auto Forex Trading System",
            },
        )

        # Plain text fallback
        plain_message = strip_tags(html_message)

        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Verification email sent to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

        return True

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to send verification email to %s: %s",
            user.email,
            str(exc),
            extra={
                "user_id": user.id,
                "email": user.email,
                "error": str(exc),
            },
            exc_info=True,
        )
        return False


def send_password_reset_email(user: "User", reset_url: str) -> bool:
    """
    Send password reset email to user.

    Args:
        user: User instance
        reset_url: Full URL for password reset

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        subject = "Reset your password - Auto Forex Trading System"

        # HTML email content
        html_message = render_to_string(
            "accounts/emails/password_reset_email.html",
            {
                "user": user,
                "reset_url": reset_url,
                "site_name": "Auto Forex Trading System",
            },
        )

        # Plain text fallback
        plain_message = strip_tags(html_message)

        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Password reset email sent to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

        return True

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to send password reset email to %s: %s",
            user.email,
            str(exc),
            extra={
                "user_id": user.id,
                "email": user.email,
                "error": str(exc),
            },
            exc_info=True,
        )
        return False


def send_welcome_email(user: "User") -> bool:
    """
    Send welcome email to user after email verification.

    Args:
        user: User instance

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        subject = "Welcome to Auto Forex Trading System!"

        # HTML email content
        html_message = render_to_string(
            "accounts/emails/welcome_email.html",
            {
                "user": user,
                "site_name": "Auto Forex Trading System",
                "login_url": f"{settings.FRONTEND_URL}/login",
            },
        )

        # Plain text fallback
        plain_message = strip_tags(html_message)

        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Welcome email sent to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

        return True

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to send welcome email to %s: %s",
            user.email,
            str(exc),
            extra={
                "user_id": user.id,
                "email": user.email,
                "error": str(exc),
            },
            exc_info=True,
        )
        return False
