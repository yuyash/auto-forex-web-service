"""Helpers for request-scoped logging metadata."""

from django.http import HttpRequest


def set_request_id(request: HttpRequest, request_id: str) -> None:
    """Attach a request ID to the Django request object."""
    setattr(request, "request_id", request_id)


def get_request_id(request: HttpRequest) -> str:
    """Return the request ID stored on the request, if any."""
    request_id = getattr(request, "request_id", None)
    return request_id if isinstance(request_id, str) and request_id else "-"
