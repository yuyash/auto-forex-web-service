"""apps.accounts.services.email

Account-owned email helpers.

Accounts must be self-contained and must not rely on apps.core for email.
This module renders the existing accounts email templates and sends mail via
AWS SES using boto3 (AWS SDK default credential chain).
"""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class AccountEmailService:
    """Service for sending account-related emails via AWS SES."""

    def __init__(self) -> None:
        # Instantiate at call sites; this class intentionally has no module-level singleton.
        pass

    def _send_email(
        self,
        *,
        to_address: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_address: str | None = None,
    ) -> bool:
        """Send an email via AWS SES.

        Uses boto3's default credential/provider chain.
        """

        resolved_from = from_address or getattr(settings, "DEFAULT_FROM_EMAIL", "")
        if not resolved_from:
            logger.error("DEFAULT_FROM_EMAIL is empty; cannot send email")
            return False

        try:
            ses = boto3.client("ses")
            ses.send_email(
                Source=resolved_from,
                Destination={"ToAddresses": [to_address]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                    },
                },
            )
            return True
        except (ClientError, BotoCoreError) as exc:
            logger.error("Failed to send SES email: %s", exc, exc_info=True)
            return False
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error sending email: %s", exc, exc_info=True)
            return False

    def send_verification_email(
        self,
        user: Any,
        verification_url: str,
        *,
        sender: type | None = None,
    ) -> bool:
        """Send a verification email to a user."""

        _ = sender  # maintained for API compatibility; unused in direct-send implementation

        try:
            context = {
                "site_name": getattr(settings, "SITE_NAME", "Auto Forex"),
                "user": user,
                "verification_url": verification_url,
            }
            html_body = render_to_string("accounts/emails/verification_email.html", context)
            text_body = strip_tags(html_body)
            subject = f"Verify your email for {context['site_name']}"
            return self._send_email(
                to_address=str(user.email),
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to send verification email: %s", exc, exc_info=True)
            return False

    def send_welcome_message(self, user: Any, *, sender: type | None = None) -> bool:
        """Send a welcome email to a user."""

        _ = sender  # maintained for API compatibility; unused in direct-send implementation

        try:
            site_name = getattr(settings, "SITE_NAME", "Auto Forex")
            base_url = getattr(settings, "FRONTEND_URL", "")
            login_url = f"{base_url}/login" if base_url else ""
            context = {
                "site_name": site_name,
                "user": user,
                "login_url": login_url,
            }
            html_body = render_to_string("accounts/emails/welcome_email.html", context)
            text_body = strip_tags(html_body)
            subject = f"Welcome to {site_name}"
            return self._send_email(
                to_address=str(user.email),
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to send welcome message: %s", exc, exc_info=True)
            return False

    def send_password_reset_email(
        self,
        user: Any,
        reset_url: str,
        *,
        sender: type | None = None,
    ) -> bool:
        """Send a password reset email to a user."""

        _ = sender  # maintained for API compatibility; unused in direct-send implementation

        try:
            site_name = getattr(settings, "SITE_NAME", "Auto Forex")
            context = {
                "site_name": site_name,
                "user": user,
                "reset_url": reset_url,
            }
            html_body = render_to_string("accounts/emails/password_reset_email.html", context)
            text_body = strip_tags(html_body)
            subject = f"Reset your {site_name} password"
            return self._send_email(
                to_address=str(user.email),
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to send password reset email: %s", exc, exc_info=True)
            return False
