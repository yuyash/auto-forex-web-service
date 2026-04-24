"""API error logging helpers and DRF exception handler."""

from __future__ import annotations

import json
from collections.abc import Mapping
from http import HTTPStatus
from logging import Logger, getLogger
from typing import Any

from django.http import HttpRequest
from django.http.request import RawPostDataException
from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.accounts.request_logging import get_request_id

logger: Logger = getLogger(__name__)

SENSITIVE_KEYS = {
    "access",
    "access_token",
    "api_key",
    "authorization",
    "cookie",
    "csrf",
    "jwt",
    "password",
    "refresh",
    "refresh_token",
    "secret",
    "token",
}
MAX_BODY_LOG_LENGTH = 2000


def _code_from_exception(exc: Exception, response: Response) -> str:
    """Return a stable machine-readable error code for a DRF response."""
    default_code = getattr(exc, "default_code", None)
    if isinstance(default_code, str) and default_code:
        return default_code
    try:
        status_name = HTTPStatus(response.status_code).phrase
    except ValueError:
        status_name = "error"
    return str(status_name).lower().replace(" ", "_").replace("-", "_")


def _stringify_error(value: Any) -> str:
    """Return a human-readable message from DRF error payloads."""
    if isinstance(value, ErrorDetail):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        detail = value.get("detail")
        if detail:
            return _stringify_error(detail)
        non_field = value.get("non_field_errors")
        if non_field:
            return _stringify_error(non_field)
        return "Validation error"
    if isinstance(value, list) and value:
        return _stringify_error(value[0])
    return "API request failed"


def standardize_error_response(exc: Exception, response: Response) -> None:
    """Ensure handled API errors expose ``error`` and ``error_code`` fields."""
    original_data = response.data
    error_code = _code_from_exception(exc, response)

    if isinstance(original_data, Mapping):
        data = dict(original_data)
        data.setdefault("error", _stringify_error(original_data))
        data.setdefault("error_code", error_code)
        response.data = data
        return

    response.data = {
        "error": _stringify_error(original_data),
        "error_code": error_code,
        "detail": original_data,
    }


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(sensitive in lowered for sensitive in SENSITIVE_KEYS)


def sanitize_for_logging(value: Any) -> Any:
    """Recursively redact sensitive values before writing logs."""
    if isinstance(value, Mapping):
        return {
            str(k): ("[REDACTED]" if _is_sensitive_key(str(k)) else sanitize_for_logging(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_for_logging(item) for item in value]
    return value


def safe_request_data(request: HttpRequest) -> Any:
    """Extract a sanitized request payload for logging."""
    data: Any = None
    try:
        data = getattr(request, "data", None)
        if data is not None:
            return sanitize_for_logging(data)
    except Exception:
        data = None

    try:
        body = getattr(request, "body", b"")
    except RawPostDataException:
        return "[unavailable]"

    if not body:
        return None

    try:
        decoded = body.decode("utf-8", errors="replace")
    except Exception:
        return "[unavailable]"

    content_type = request.META.get("CONTENT_TYPE", "")
    if "json" in content_type.lower():
        try:
            return sanitize_for_logging(json.loads(decoded))
        except Exception:
            return "[unparseable json body]"

    if len(decoded) > MAX_BODY_LOG_LENGTH:
        return f"{decoded[:MAX_BODY_LOG_LENGTH]}...[truncated]"
    return decoded


def build_request_log_context(request: HttpRequest) -> dict[str, Any]:
    """Build a sanitized request context payload for structured logs."""
    user = getattr(request, "user", None)
    resolver_match = getattr(request, "resolver_match", None)

    return {
        "request_id": get_request_id(request),
        "method": getattr(request, "method", "-"),
        "path": getattr(request, "path", "-"),
        "query_params": sanitize_for_logging(dict(request.GET.items())),
        "content_type": request.META.get("CONTENT_TYPE", ""),
        "user_id": getattr(user, "pk", None) if getattr(user, "is_authenticated", False) else None,
        "username": getattr(user, "username", None)
        if getattr(user, "is_authenticated", False)
        else None,
        "client_ip": request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", ""),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "view_name": getattr(resolver_match, "view_name", None),
        "route": getattr(resolver_match, "route", None),
        "url_kwargs": sanitize_for_logging(getattr(resolver_match, "kwargs", {})),
    }


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Log DRF exceptions with request context, then delegate to DRF."""
    response = drf_exception_handler(exc, context)
    request = context.get("request")
    view = context.get("view")

    if request is None:
        if response is None:
            logger.exception("Unhandled API exception without request context")
        else:
            logger.warning(
                "Handled API exception without request context",
                extra={
                    "status_code": response.status_code,
                    "exception_class": type(exc).__name__,
                },
            )
        return response

    log_context = build_request_log_context(request)
    log_context.update(
        {
            "exception_class": type(exc).__name__,
            "exception": str(exc),
            "view_class": view.__class__.__name__ if view is not None else None,
            "view_action": getattr(view, "action", None) if view is not None else None,
            "request_data": safe_request_data(request),
        }
    )

    if response is None:
        logger.exception("Unhandled API exception", extra=log_context)
        return None

    standardize_error_response(exc, response)

    log_context["status_code"] = response.status_code
    try:
        log_context["response_data"] = sanitize_for_logging(response.data)
    except Exception:
        log_context["response_data"] = "[unavailable]"

    message = "API request failed"
    if response.status_code >= 500:
        logger.error(message, extra=log_context, exc_info=exc)
    else:
        logger.warning(message, extra=log_context)
    return response
