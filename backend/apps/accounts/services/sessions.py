"""Helpers for binding auth flows to a stable per-client UserSession."""

from __future__ import annotations

from typing import Any

from apps.accounts.models import User, UserSession


def ensure_request_session_key(request: Any) -> str | None:
    """Return a stable Django session key for this request.

    DRF requests still pass through ``SessionMiddleware``, but anonymous API
    requests may not have a persisted session key yet.  Saving the session
    creates one so we can bind refresh-token families to a specific browser.
    """

    session = getattr(request, "session", None)
    if session is None:
        return None

    session_key = getattr(session, "session_key", None)
    if not session_key:
        session.save()
        session_key = getattr(session, "session_key", None)

    return str(session_key) if session_key else None


def get_or_create_user_session(
    request: Any,
    user: User,
    *,
    ip_address: str,
    user_agent: str,
) -> UserSession | None:
    """Return the current browser's UserSession, creating it when needed."""

    session_key = ensure_request_session_key(request)
    if not session_key:
        return None

    session, created = UserSession.objects.get_or_create(
        session_key=session_key,
        defaults={
            "user": user,
            "ip_address": ip_address,
            "user_agent": user_agent or "",
            "is_active": True,
        },
    )
    if created:
        return session

    update_fields: list[str] = []
    if session.user_id != user.pk:
        session.user = user
        update_fields.append("user")
    if session.ip_address != ip_address:
        session.ip_address = ip_address
        update_fields.append("ip_address")
    if session.user_agent != (user_agent or ""):
        session.user_agent = user_agent or ""
        update_fields.append("user_agent")
    if not session.is_active:
        session.is_active = True
        session.logout_time = None
        update_fields.extend(["is_active", "logout_time"])

    if update_fields:
        session.save(update_fields=update_fields)

    return session


def get_user_session_for_request(request: Any, user: User) -> UserSession | None:
    """Return the tracked UserSession for the current request if one exists."""

    session_key = ensure_request_session_key(request)
    if not session_key:
        return None

    return UserSession.objects.filter(user=user, session_key=session_key).first()
