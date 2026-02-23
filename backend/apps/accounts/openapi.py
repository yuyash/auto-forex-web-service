"""OpenAPI schema extensions for accounts app."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationExtension(OpenApiAuthenticationExtension):
    """Register JWTAuthentication with drf-spectacular."""

    target_class = "apps.accounts.auth.JWTAuthentication"
    name = "JWTAuth"

    def get_security_definition(self, auto_schema):
        """Return Bearer token security scheme."""
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
