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


def _get_system_setting(key: str, default: Any) -> Any:
    """Fetch a system setting with graceful fallback."""
    try:
        from accounts.settings_helper import (  # pylint: disable=import-outside-toplevel
            get_system_setting,
        )

        return get_system_setting(key, default)
    except Exception:  # pylint: disable=broad-except
        return default


def _resolve_from_email(default: str) -> str:
    return str(_get_system_setting("default_from_email", default))


def _resolve_email_backend_type(default: str = "smtp") -> str:
    backend = _get_system_setting("email_backend_type", default)
    if isinstance(backend, str):
        return backend.lower()
    return str(default).lower()


def _get_aws_config() -> dict[str, Any]:
    """Get AWS configuration from system settings and environment."""
    return {
        "credential_method": _get_system_setting("aws_credential_method", "access_keys"),
        "aws_profile": _get_system_setting("aws_profile_name", os.environ.get("AWS_PROFILE")),
        "aws_role_arn": _get_system_setting("aws_role_arn", os.environ.get("AWS_ROLE_ARN")),
        "aws_credentials_file": _get_system_setting(
            "aws_credentials_file_path", os.environ.get("AWS_CREDENTIALS_FILE")
        ),
        "access_key": _get_system_setting("aws_access_key_id", os.environ.get("AWS_ACCESS_KEY_ID")),
        "secret_key": _get_system_setting(
            "aws_secret_access_key", os.environ.get("AWS_SECRET_ACCESS_KEY")
        ),
    }


def _log_aws_config(config: dict[str, Any]) -> None:
    """Log AWS configuration for debugging."""
    logger.info(
        "AWS Configuration - Method: %s, Profile: %s, Role ARN: %s, Has Access Key: %s",
        config["credential_method"],
        config["aws_profile"] or "None",
        config["aws_role_arn"] or "None",
        "Yes" if config["access_key"] else "No",
    )


def _check_aws_files(aws_profile: str | None) -> None:
    """Check AWS credentials and config files accessibility."""
    aws_creds_path = os.path.expanduser("~/.aws/credentials")
    aws_config_path = os.path.expanduser("~/.aws/config")
    logger.info(
        "AWS files accessibility - credentials: %s, config: %s",
        "exists" if os.path.exists(aws_creds_path) else "NOT FOUND",
        "exists" if os.path.exists(aws_config_path) else "NOT FOUND",
    )

    if aws_profile and os.path.exists(aws_config_path):
        try:
            with open(aws_config_path, "r", encoding="utf-8") as f:
                config_content = f.read()
                if (
                    f"[profile {aws_profile}]" in config_content
                    or f"[{aws_profile}]" in config_content
                ):
                    logger.info("Profile '%s' found in config file", aws_profile)
                else:
                    logger.warning("Profile '%s' NOT found in config file", aws_profile)
        except Exception as e:
            logger.error("Failed to read config file: %s", e)


def _create_base_session(config: dict[str, Any]) -> Any:
    """Create base boto3 session based on credential method."""
    import boto3  # pylint: disable=import-error

    credential_method = config["credential_method"]
    aws_credentials_file = config["aws_credentials_file"]
    aws_profile = config["aws_profile"]
    access_key = config["access_key"]
    secret_key = config["secret_key"]

    # Handle custom credentials file
    if credential_method == "credentials_file" and aws_credentials_file:
        logger.info("Using AWS credentials file: %s", aws_credentials_file)
        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = aws_credentials_file

    # Create session with access keys
    if credential_method == "access_keys" and access_key and secret_key:
        logger.info("Using AWS access key credentials from system settings")
        return boto3.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    # Create session with profile
    session_kwargs: dict[str, str] = {}
    if credential_method in {"profile", "profile_role"} and aws_profile:
        logger.info("Using AWS profile: %s", aws_profile)
        session_kwargs["profile_name"] = aws_profile

    if not session_kwargs:
        logger.info("Using default AWS credentials chain")
    logger.info("Creating boto3 session with kwargs: %s", session_kwargs)
    return boto3.Session(**session_kwargs)


def _verify_session_credentials(session: Any) -> None:
    """Verify that session has valid credentials."""
    try:
        credentials = session.get_credentials()
        if credentials:
            logger.info(
                "Successfully retrieved credentials from session. Access Key ID: %s...",
                credentials.access_key[:10] if credentials.access_key else "None",
            )
        else:
            logger.warning("Session created but no credentials found")
    except Exception as e:
        logger.error("Failed to retrieve credentials from session: %s", e)


def _assume_role(session: Any, role_arn: str) -> Any:
    """Assume AWS role using STS and return new session."""
    import boto3  # pylint: disable=import-error
    from botocore.exceptions import ClientError  # pylint: disable=import-error

    logger.info("Attempting to assume AWS role: %s", role_arn)

    try:
        sts_client = session.client("sts")

        # Verify current identity
        try:
            caller_identity = sts_client.get_caller_identity()
            logger.info(
                "Current AWS identity - Account: %s, ARN: %s",
                caller_identity.get("Account"),
                caller_identity.get("Arn"),
            )
        except Exception as e:
            logger.error("Failed to get caller identity: %s", e)

        # Assume role
        logger.info("Calling assume_role with RoleArn: %s", role_arn)
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="forex-trading-email",
            DurationSeconds=3600,
        )

        credentials = response["Credentials"]
        logger.info(
            "Role assumed successfully! Expires at: %s, Access Key: %s...",
            credentials["Expiration"],
            credentials["AccessKeyId"][:10],
        )

        # Create new session with assumed role credentials
        new_session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )

        # Verify assumed role identity
        try:
            assumed_sts = new_session.client("sts")
            assumed_identity = assumed_sts.get_caller_identity()
            logger.info(
                "Assumed role identity - Account: %s, ARN: %s",
                assumed_identity.get("Account"),
                assumed_identity.get("Arn"),
            )
        except Exception as e:
            logger.error("Failed to verify assumed role identity: %s", e)

        return new_session

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            "Failed to assume role - Error Code: %s, Message: %s", error_code, error_message
        )
        raise
    except Exception as e:
        logger.error("Unexpected error during role assumption: %s", e)
        raise


def get_aws_session() -> Any:
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
        from botocore.exceptions import BotoCoreError, ClientError  # pylint: disable=import-error

        # Get configuration
        config = _get_aws_config()
        _log_aws_config(config)
        _check_aws_files(config["aws_profile"])

        # Create base session
        session = _create_base_session(config)
        _verify_session_credentials(session)

        # Assume role if needed
        if config["credential_method"] == "profile_role" and config["aws_role_arn"]:
            session = _assume_role(session, config["aws_role_arn"])

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
        from botocore.exceptions import BotoCoreError, ClientError  # pylint: disable=import-error

        # Get AWS session with proper authentication
        session = get_aws_session()

        # Create SES client
        region = _get_system_setting(
            "aws_ses_region",
            getattr(settings, "AWS_SES_REGION", "us-east-1"),
        )
        ses_client = session.client("ses", region_name=region)

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
    email_backend = _resolve_email_backend_type(getattr(settings, "EMAIL_BACKEND_TYPE", "smtp"))
    resolved_from_email = _resolve_from_email(from_email)

    if email_backend == "ses":
        return _send_email_via_ses(
            subject=subject,
            html_message=html_message,
            plain_message=plain_message,
            from_email=resolved_from_email,
            recipient_list=recipient_list,
        )

    # Use Django's default SMTP backend
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=resolved_from_email,
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
    subject = "Verify your email address - Auto Forex Trader"

    # HTML email content
    html_message = render_to_string(
        "accounts/emails/verification_email.html",
        {
            "user": user,
            "verification_url": verification_url,
            "site_name": "Auto Forex Trader",
        },
    )

    # Plain text fallback
    plain_message = strip_tags(html_message)

    # Send email using configured backend
    success = _send_email(
        subject=subject,
        html_message=html_message,
        plain_message=plain_message,
        from_email=_resolve_from_email(settings.DEFAULT_FROM_EMAIL),
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
    subject = "Reset your password - Auto Forex Trader"

    # HTML email content
    html_message = render_to_string(
        "accounts/emails/password_reset_email.html",
        {
            "user": user,
            "reset_url": reset_url,
            "site_name": "Auto Forex Trader",
        },
    )

    # Plain text fallback
    plain_message = strip_tags(html_message)

    # Send email using configured backend
    success = _send_email(
        subject=subject,
        html_message=html_message,
        plain_message=plain_message,
        from_email=_resolve_from_email(settings.DEFAULT_FROM_EMAIL),
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
    subject = "Welcome to Auto Forex Trader!"

    # HTML email content
    html_message = render_to_string(
        "accounts/emails/welcome_email.html",
        {
            "user": user,
            "site_name": "Auto Forex Trader",
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
        from_email=_resolve_from_email(settings.DEFAULT_FROM_EMAIL),
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
