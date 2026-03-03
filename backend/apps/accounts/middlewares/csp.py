"""Content Security Policy middleware.

Adds a ``Content-Security-Policy`` header to every response to mitigate XSS
attacks — the primary threat when tokens are stored in ``localStorage``.
"""

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class CSPMiddleware:
    """Inject Content-Security-Policy header into all responses."""

    def __init__(self, get_response):  # noqa: ANN001
        self.get_response = get_response
        self._header_value = self._build_header()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self._header_value
        return response

    @staticmethod
    def _build_header() -> str:
        directives = {
            "default-src": getattr(settings, "CSP_DEFAULT_SRC", "'self'"),
            "script-src": getattr(settings, "CSP_SCRIPT_SRC", "'self'"),
            "style-src": getattr(settings, "CSP_STYLE_SRC", "'self' 'unsafe-inline'"),
            "img-src": getattr(settings, "CSP_IMG_SRC", "'self' data:"),
            "connect-src": getattr(settings, "CSP_CONNECT_SRC", "'self'"),
            "frame-ancestors": "'none'",
            "base-uri": "'self'",
            "form-action": "'self'",
        }
        return "; ".join(f"{k} {v}" for k, v in directives.items())
