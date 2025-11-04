"""
Email utilities for sending verification and notification emails.

This module contains utilities for:
- Sending email verification emails
- Sending password reset emails
- Sending notification emails

Supports two email backends:
- SMTP: Traditional email server (default Django backend)
- AWS SES: Amazon Simple Email Service using boto3

Requirements: 1.4, 1.5
"""

import logging
import os
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

if TYPE_CHECKING:
    from accounts.models import User

logger = logging.getLogger(__name__)


def _get_aws_session() -> Any:
    """
    Create AWS boto3 session with proper authentication.

    Uses the same authentication as backtesting:
    1. AWS_PROFILE environment variable (profile-based)
    2. AWS_ROLE_ARN environment variable (role assumption with STS)
    3. AWS_CREDENTIALS_FILE (custom credentials location)
    4. IAM role (default for EC2/ECS instances)

    Returns:
        Configured boto3 session

    Raises:
        RuntimeError: If AWS client initialization fails
    """
    try:
        # pylint: disable=import-error
        import boto3  # type: ignore[import-untyped]  # noqa: E501
        from botocore.exceptions import (  # type: ignore[import-untyped]  # noqa: E501
            BotoCoreError,
            ClientError,
        )

        # Check for AWS configuration environment variables
        aws_profile = os.environ.get("AWS_PROFILE")
        aws_role_arn = os.environ.get("AWS_ROLE_ARN")
        aws_credentials_file = os.environ.get("AWS_CREDENTIALS_FILE")

        session_kwargs: dict[str, str] = {}

        # Handle custom credentials file
        if aws_credentials_file:
            logger.info("Using AWS credentials file: %s", aws_credentials_file)
            os.environ["AWS_SHARED_CREDENTIALS_FILE"] = aws_credentials_file

        # Create base session with profile if specified
        if aws_profile:
            logger.info("Using AWS profile: %s", aws_profile)
            session_kwargs["profile_name"] = aws_profile
        else:
            logger.info("Using default AWS credentials chain")

        # Create boto3 session
        session = boto3.Session(**session_kwargs)

        # If role ARN is specified, assume the role using STS
        if aws_role_arn:
            logger.info("Assuming AWS role: %s", aws_role_arn)

            # Create STS client
            sts_client = session.client("sts")

            # Assume role
            response = sts_client.assume_role(
                RoleArn=aws_role_arn,
                RoleSessionName="forex-trading-email",
                DurationSeconds=3600,  # 1 hour
            )

            # Extract credentials
            credentials = response["Credentials"]
            logger.info(
                "Role assumed successfully, expires at: %s",
                credentials["Expiration"],
            )

            # Create new session with assumed role credentials
            session = boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )
            logger.info("Successfully assumed role")

        return session

    except (BotoCoreError, ClientError) as exc:
        logger.error("Failed to initialize AWS session: %s", exc)
        raise RuntimeError(f"AWS session initialization failed: {exc}") from exc


def _send_email_via_ses(
    subject: str,
    html_message: str,
    plain_message: str,
    from_email: str,
    recipient_list: list[str],
) -> bool:
    """
    Send email using AWS SES via boto3.

    Uses the same AWS authentication as backtesting:
    - AWS_PROFILE environment variable (profile-based)
    - AWS_ROLE_ARN environment variable (role assumption)
    - AWS_CREDENTIALS_FILE (custom credentials location)
    - IAM role (default for EC2/ECS)

    Args:
        subject: Email subject
        html_message: HTML email content
        plain_message: Plain text email content
        from_email: Sender email address
        recipient_list: List of recipient email addresses

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # pylint: disable=import-error
        from botocore.exceptions import BotoCoreError, ClientError  # noqa: E501

        # Get AWS session with proper authentication
        session = _get_aws_session()

        # Create SES client
        ses_client = session.client(
            "ses",
            region_name=getattr(settings, "AWS_SES_REGION", "us-east-1"),
        )

        # Send email
        response = ses_client.send_email(
            Source=from_email,
            Destination={
                "ToAddresses": recipient_list,
            },
            Message={
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": plain_message,
                        "Charset": "UTF-8",
                    },
                    "Html": {
                        "Data": html_message,
                        "Charset": "UTF-8",
                    },
                },
            },
        )

        logger.info(
            "Email sent via AWS SES to %s (MessageId: %s)",
            ", ".join(recipient_list),
            response.get("MessageId"),
            extra={
                "recipients": recipient_list,
                "message_id": response.get("MessageId"),
                "backend": "ses",
            },
        )

        return True

    except (BotoCoreError, ClientError) as exc:
        logger.error(
            "Failed to send email via AWS SES: %s",
            str(exc),
            extra={
                "recipients": recipient_list,
                "error": str(exc),
                "backend": "ses",
            },
            exc_info=True,
        )
        return False
    except ImportError:
        logger.error(
            "boto3 not installed. Install with: pip install boto3",
            extra={
                "recipients": recipient_list,
                "backend": "ses",
            },
        )
        return False


def _send_email(
    subject: str,
    html_message: str,
    plain_message: str,
    from_email: str,
    recipient_list: list[str],
) -> bool:
    """
    Send email using configured backend (SMTP or AWS SES).

    Args:
        subject: Email subject
        html_message: HTML email content
        plain_message: Plain text email content
        from_email: Sender email address
        recipient_list: List of recipient email addresses

    Returns:
        True if email sent successfully, False otherwise
    """
    email_backend = getattr(settings, "EMAIL_BACKEND_TYPE", "smtp").lower()

    if email_backend == "ses":
        return _send_email_via_ses(
            subject=subject,
            html_message=html_message,
            plain_message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
        )

    # Use Django's default SMTP backend
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Email sent via SMTP to %s",
            ", ".join(recipient_list),
            extra={
                "recipients": recipient_list,
                "backend": "smtp",
            },
        )

        return True

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to send email via SMTP: %s",
            str(exc),
            extra={
                "recipients": recipient_list,
                "error": str(exc),
                "backend": "smtp",
            },
            exc_info=True,
        )
        return False


def send_verification_email(user: "User", verification_url: str) -> bool:
    """
    Send email verification email to user.

    Args:
        user: User instance
        verification_url: Full URL for email verification

    Returns:
        True if email sent successfully, False otherwise
    """
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

    # Send email using configured backend
    success = _send_email(
        subject=subject,
        html_message=html_message,
        plain_message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )

    if success:
        logger.info(
            "Verification email sent to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )
    else:
        logger.error(
            "Failed to send verification email to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

    return success


def send_password_reset_email(user: "User", reset_url: str) -> bool:
    """
    Send password reset email to user.

    Args:
        user: User instance
        reset_url: Full URL for password reset

    Returns:
        True if email sent successfully, False otherwise
    """
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

    # Send email using configured backend
    success = _send_email(
        subject=subject,
        html_message=html_message,
        plain_message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )

    if success:
        logger.info(
            "Password reset email sent to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )
    else:
        logger.error(
            "Failed to send password reset email to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

    return success


def send_welcome_email(user: "User") -> bool:
    """
    Send welcome email to user after email verification.

    Args:
        user: User instance

    Returns:
        True if email sent successfully, False otherwise
    """
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

    # Send email using configured backend
    success = _send_email(
        subject=subject,
        html_message=html_message,
        plain_message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )

    if success:
        logger.info(
            "Welcome email sent to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )
    else:
        logger.error(
            "Failed to send welcome email to %s",
            user.email,
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

    return success
